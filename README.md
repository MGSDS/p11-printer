# p11-printer

Disclaimer: documentrarion adaptation done by AI

Python CLI and library for the **P11 Bluetooth thermal label printer** (LeMinyun / Xiamen Lexi Electronic Technology).

Forked from [fichero-printer](https://github.com/0xMH/fichero-printer) by [@0xMH](https://github.com/0xMH) — all protocol reverse-engineering credit goes to them. This fork adapts the library specifically for the P11-GZP printer and adds a `print_raster` convenience method.

## Changes from upstream

- Package renamed `fichero` → `p11`, CLI command `fichero` → `p11`
- BLE service changed from `18f0` to `ff00` (`ff02`/`ff01`) — required for P11
- `set_paper_type` sends fire-and-forget (P11 does not ACK this command)
- `print_raster(img)` method added — accepts a PIL Image, handles GS v 0 encoding internally
- Classic Bluetooth (RFCOMM) transport removed — P11 uses BLE only
- Name prefix filter changed to `P11_`

## The printer

- Model: `P11-GZP`, BLE name: `P11_XXXX`
- Android app: LeMinyun Print (`com.lexi.print`)
- 96px wide printhead, 203 DPI
- 14mm × 30mm self-adhesive labels (96×240 dots)
- BLE service: `ff00`, write: `ff02`, notify: `ff01`

## Setup

```bash
pip install -e .
```

Turn on printer, then:

```bash
p11 info
```

To skip scanning on subsequent runs:

```bash
export FICHERO_ADDR=AA:BB:CC:DD:EE:FF
```

## CLI Usage

```bash
p11 info                        # device info + battery
p11 status                      # detailed status

p11 text "Hello World"          # print text
p11 text "Fragile" --copies 3
p11 image label.png             # print image file

p11 set density 2               # 0=light 1=medium 2=thick
p11 set shutdown 30             # auto-off minutes
p11 set paper gap               # gap | black | continuous
```

## Library Usage

```python
import asyncio
from p11 import connect

async def main():
    async with connect() as pc:
        print(await pc.get_info())
        await pc.set_paper_type()
        await pc.wakeup()
        await pc.enable()
        await pc.print_raster(img)  # PIL Image
        await pc.form_feed()
        await pc.stop_print()

asyncio.run(main())
```

## Protocol notes

- Image command: `GS v 0` raster (ESC * does NOT work over BLE on P11)
- Eject: `1D 0C` (GS FF) — same as D11s
- `set_paper_type` (`10 FF 84 00`) — P11 executes it silently, no ACK
- `stop_print` (`10 FF FE 45`) — returns `OK`

See [docs/PROTOCOL.md](docs/PROTOCOL.md) for the full command reference (from upstream, verified against D11s; P11 differences noted above).

## License

MIT
