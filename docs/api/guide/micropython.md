# MicroPython notes

## RAM use

Measured in CI on MicroPython v1.25.0 (unix port), importing the library, creating a [`UPS`][ups_hat.board.UPS] on the register simulator and polling it twice. The 32-bit build is the closest match to RP2040, RP2350 and ESP32 boards.

| Build | Files | RAM in use after import | RAM in use while running | Smallest heap that works |
|---|---|---|---|---|
| 32-bit | `.mpy` (recommended) | 68 KB | 72 KB | 90 KB |
| 32-bit | `.py` (compiled on the board) | 72 KB | 77 KB | 130 KB |
| 64-bit | `.mpy` | 101 KB | 109 KB | 142 KB |
| 64-bit | `.py` | 107 KB | 114 KB | 195 KB |

- **"Smallest heap that works"** is the figure to compare with your board: run `import gc; gc.collect(); print(gc.mem_free())` before importing anything. It includes the extra memory the compiler needs while it reads `.py` files, which is why `.py` needs about 40 KB more than `.mpy`.
- **`.mpy` files are recommended.** They skip on-board compilation and leave the most RAM for your own code. Get them from the [latest release](https://github.com/PinGoblin/UPS_HAT/releases/latest); see [Installation](install.md).
- **To save more RAM**, freeze the package into the firmware. The library's code then runs from flash and only its working data uses the heap.
- The figures are measured on the unix port, not on a board. Real boards also need RAM for your own program and for drivers such as Wi-Fi. CI re-measures on every pull request: see the `micropython` job's summary.

## Other notes

- Docstrings are discarded when MicroPython compiles the code, so they cost no RAM. They do take flash space in the `.py` files; `.mpy` files leave them out.
- The command-line tool and Pi 5 monitoring are not available on MicroPython. Pass `pi_monitor=False`.
- `state_file` works on boards with a filesystem, but flash wears with frequent writes. The library saves at most every 5 minutes.

## Example

`examples/micropython_main.py`:

```python
import time
from machine import I2C, Pin
from ups_hat import UPS, CRITICAL

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
ups = UPS(i2c, cells_parallel=1, cell_capacity_mah=3000, pi_monitor=False)

while True:
    s = ups.poll()
    print(s.vbat, s.ibat, s.soc, s.fault_codes())
    time.sleep(2)
```
