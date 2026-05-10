# p11-printer

Python CLI and library for the P11 Bluetooth thermal label printer (LeMinyun / Xiamen Lexi Electronic Technology).

Reverse-engineered by BLE sniffing the LeMinyun Android app. Based on [fichero-printer](https://github.com/0xMH/fichero-printer) (same AiYin/LuckPrinter SDK internals).

## The printer

- Model: `P11-GZP`, BLE name: `P11_XXXX`
- 96px wide printhead, 203 DPI
- 14mm × 30mm self-adhesive labels (96×240 dots)
- BLE only (macOS/Linux/Windows via `bleak`)
- Android app: LeMinyun Print (`com.lexi.print`)

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

- BLE service: `ff00`, write: `ff02`, notify: `ff01`
- Image command: `GS v 0` raster (ESC * does NOT work over BLE)
- Eject: `1D 0C` (GS FF)
- `set_paper_type` (`10 FF 84 00`) fires without ACK — P11 does not respond to it
- `stop_print` (`10 FF FE 45`) returns `OK`

## License

MIT
