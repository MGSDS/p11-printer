"""
P11 thermal label printer - BLE interface.

Protocol reverse-engineered from decompiled LeMinyun APK.
Device class: AiYinNormalDevice (LuckPrinter SDK)
96px wide printhead (12 bytes/row), 203 DPI, prints 1-bit raster images.

Modified by mgsds to work with other generic printer named P11.
Do not now what this printer is but it uses app called LeMinyun.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from bleak import BleakClient, BleakGATTCharacteristic, BleakScanner

PRINTER_NAME_PREFIXES = ("P11_",)

WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"

PRINTHEAD_PX = 96
BYTES_PER_ROW = PRINTHEAD_PX // 8  # 12
CHUNK_SIZE = 200

PAPER_GAP = 0x00
PAPER_BLACK_MARK = 0x01
PAPER_CONTINUOUS = 0x02

DELAY_COMMAND_GAP = 0.05
DELAY_CHUNK_GAP = 0.02
DELAY_RASTER_SETTLE = 0.50
DELAY_AFTER_FEED = 0.30
DELAY_NOTIFY_EXTRA = 0.05


class PrinterError(Exception):
    pass


class PrinterNotFound(PrinterError):
    pass


class PrinterTimeout(PrinterError):
    pass


class PrinterNotReady(PrinterError):
    pass


async def find_printer() -> str:
    print("Scanning for printer...")
    devices = await BleakScanner.discover(timeout=8)
    for d in devices:
        if d.name and any(d.name.startswith(p) for p in PRINTER_NAME_PREFIXES):
            print(f"  Found {d.name} at {d.address}")
            return d.address
    raise PrinterNotFound("No P11 printer found. Is it turned on?")


class PrinterStatus:
    def __init__(self, byte: int):
        self.raw = byte
        self.printing = bool(byte & 0x01)
        self.cover_open = bool(byte & 0x02)
        self.no_paper = bool(byte & 0x04)
        self.low_battery = bool(byte & 0x08)
        self.overheated = bool(byte & 0x10 or byte & 0x40)
        self.charging = bool(byte & 0x20)

    def __str__(self) -> str:
        flags = [
            k
            for k, v in {
                "printing": self.printing,
                "cover open": self.cover_open,
                "no paper": self.no_paper,
                "low battery": self.low_battery,
                "overheated": self.overheated,
                "charging": self.charging,
            }.items()
            if v
        ]
        return ", ".join(flags) if flags else "ready"

    @property
    def ok(self) -> bool:
        return not (self.cover_open or self.no_paper or self.overheated)


class PrinterClient:
    def __init__(self, client: BleakClient):
        self.client = client
        self._buf = bytearray()
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()

    def _on_notify(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        self._buf.extend(data)
        self._event.set()

    async def start(self) -> None:
        await self.client.start_notify(NOTIFY_UUID, self._on_notify)

    async def send(
        self, data: bytes, wait: bool = False, timeout: float = 2.0
    ) -> bytes:
        async with self._lock:
            if wait:
                self._buf.clear()
                self._event.clear()
            await self.client.write_gatt_char(WRITE_UUID, data, response=False)
            if wait:
                try:
                    await asyncio.wait_for(self._event.wait(), timeout=timeout)
                    await asyncio.sleep(DELAY_NOTIFY_EXTRA)
                except asyncio.TimeoutError:
                    raise PrinterTimeout(f"No response within {timeout}s")
            return bytes(self._buf)

    async def send_chunked(self, data: bytes) -> None:
        async with self._lock:
            for i in range(0, len(data), CHUNK_SIZE):
                await self.client.write_gatt_char(
                    WRITE_UUID, data[i : i + CHUNK_SIZE], response=False
                )
                await asyncio.sleep(DELAY_CHUNK_GAP)

    # --- Info ---

    async def get_model(self) -> str:
        r = await self.send(bytes([0x10, 0xFF, 0x20, 0xF0]), wait=True)
        return r.decode(errors="replace").strip() if r else "?"

    async def get_firmware(self) -> str:
        r = await self.send(bytes([0x10, 0xFF, 0x20, 0xF1]), wait=True)
        return r.decode(errors="replace").strip() if r else "?"

    async def get_serial(self) -> str:
        r = await self.send(bytes([0x10, 0xFF, 0x20, 0xF2]), wait=True)
        return r.decode(errors="replace").strip() if r else "?"

    async def get_boot_version(self) -> str:
        r = await self.send(bytes([0x10, 0xFF, 0x20, 0xEF]), wait=True)
        return r.decode(errors="replace").strip() if r else "?"

    async def get_battery(self) -> int:
        r = await self.send(bytes([0x10, 0xFF, 0x50, 0xF1]), wait=True)
        return r[-1] if r and len(r) >= 2 else -1

    async def get_status(self) -> PrinterStatus:
        r = await self.send(bytes([0x10, 0xFF, 0x40]), wait=True)
        return PrinterStatus(r[-1]) if r else PrinterStatus(0xFF)

    async def get_all_info(self) -> dict:
        r = await self.send(bytes([0x10, 0xFF, 0x70]), wait=True)
        if not r:
            return {}
        parts = r.decode(errors="replace").split("|")
        if len(parts) >= 6:
            return {
                "bt_name": parts[0],
                "mac_classic": parts[1],
                "mac_ble": parts[2],
                "firmware": parts[3],
                "serial": parts[4],
                "battery": f"{parts[5]}%",
            }
        return {"raw": r.decode(errors="replace")}

    async def get_info(self) -> dict:
        status = await self.get_status()
        return {
            "model": await self.get_model(),
            "firmware": await self.get_firmware(),
            "boot": await self.get_boot_version(),
            "serial": await self.get_serial(),
            "battery": f"{await self.get_battery()}%",
            "status": str(status),
            "shutdown": f"{await self.get_shutdown_time()} min",
        }

    # --- Config ---

    async def get_density(self) -> bytes:
        return await self.send(bytes([0x10, 0xFF, 0x11]), wait=True)

    async def get_shutdown_time(self) -> int:
        r = await self.send(bytes([0x10, 0xFF, 0x13]), wait=True)
        return ((r[0] << 8) | r[1]) if r and len(r) >= 2 else -1

    async def set_density(self, level: int) -> bool:
        r = await self.send(bytes([0x10, 0xFF, 0x10, 0x00, level]), wait=True)
        return r == b"OK"

    async def set_paper_type(self, paper: int = PAPER_GAP) -> None:
        """0=gap/label, 1=black mark, 2=continuous. P11 does not ACK."""
        await self.send(bytes([0x10, 0xFF, 0x84, paper]), wait=False)

    async def set_shutdown_time(self, minutes: int) -> bool:
        r = await self.send(
            bytes([0x10, 0xFF, 0x12, (minutes >> 8) & 0xFF, minutes & 0xFF]), wait=True
        )
        return r == b"OK"

    async def factory_reset(self) -> bool:
        r = await self.send(bytes([0x10, 0xFF, 0x04]), wait=True)
        return r == b"OK"

    # --- Print ---

    async def wakeup(self) -> None:
        await self.send(b"\x00" * 12)

    async def enable(self) -> None:
        await self.send(bytes([0x10, 0xFF, 0xFE, 0x01]))

    async def print_raster(self, img: "Image.Image") -> None:
        from p11.imaging import image_to_raster, prepare_image

        prepped = prepare_image(img)
        raster = image_to_raster(prepped)
        rows = prepped.height
        header = bytes(
            [
                0x1D,
                0x76,
                0x30,
                0x00,
                BYTES_PER_ROW,
                0x00,
                rows & 0xFF,
                (rows >> 8) & 0xFF,
            ]
        )
        await self.send_chunked(header + raster)

    async def feed_dots(self, dots: int) -> None:
        await self.send(bytes([0x1B, 0x4A, dots & 0xFF]))

    async def form_feed(self) -> None:
        await self.send(bytes([0x1D, 0x0C]))

    async def stop_print(self) -> bool:
        r = await self.send(bytes([0x10, 0xFF, 0xFE, 0x45]), wait=True, timeout=60.0)
        return bool(r) and (r[0] == 0xAA or r.startswith(b"OK"))


@asynccontextmanager
async def connect(address: str | None = None) -> AsyncGenerator[PrinterClient, None]:
    addr = address or await find_printer()
    async with BleakClient(addr) as client:
        pc = PrinterClient(client)
        await pc.start()
        yield pc
