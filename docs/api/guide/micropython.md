# MicroPython notes

The library has the same interface on MicroPython and on the Raspberry Pi. This page lists every difference.

## Differences from the Raspberry Pi

| Feature | Raspberry Pi | MicroPython |
|---|---|---|
| I²C bus | Opened automatically (`/dev/i2c-1`) | Pass your `machine.I2C` object to `UPS` |
| Pi 5 supply monitoring (`pi_monitor`) | ✓ | ✗ Pass `pi_monitor=False` |
| `ups-hat` command-line tool | ✓ | ✗ |
| Power-off integration (service and shutdown hook) | ✓ | ✗ |
| `state_file` | ✓ | ✓ On boards with a filesystem. The library saves at most every 5 minutes to limit flash wear. |

## Free RAM needed

Check the free RAM on your board before importing anything:

```python
import gc; gc.collect(); print(gc.mem_free())
```

| Board | Files | Free RAM needed |
|---|---|---|
| 32-bit (RP2040, RP2350, ESP32) | `.mpy` (recommended) | 90 KB |
| 32-bit (RP2040, RP2350, ESP32) | `.py` | 130 KB |
| 64-bit | `.mpy` | 142 KB |
| 64-bit | `.py` | 195 KB |

Figures are for MicroPython 1.25. Your own program and drivers such as Wi-Fi need RAM on top of these.

- **Use the `.mpy` files.** The board does not need to compile them, which saves 40 KB. Get them from the [latest release](https://github.com/PinGoblin/UPS_HAT/releases/latest): See [Installation](install.md).
- **To save more RAM**, freeze the package into the firmware. The library's code then runs from flash and only its working data uses RAM.
- Docstrings cost no RAM: MicroPython discards them when it compiles the code.

## Example

`examples/micropython_main.py` prints the battery state every 2 s and lights the board's LED on a critical fault. Run it on a PC without hardware with `micropython examples/micropython_main.py --mock` from a copy of the repository.

```python
import time
from machine import I2C, Pin
from ups_hat import UPS, UPSError, CRITICAL

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
try:
    ups = UPS(i2c, cells_parallel=1, cell_capacity_mah=3000, pi_monitor=False)
except UPSError as e:
    print("UPS HAT+ not available:", e)
    raise SystemExit(1)

led = Pin("LED", Pin.OUT)
ups.on_fault(lambda f: print("FAULT", f))

while True:
    s = ups.poll()
    print(s.vbat, s.ibat, s.soc, s.fault_codes())
    led.value(1 if s.worst_severity() >= CRITICAL else 0)
    time.sleep(2)
```
