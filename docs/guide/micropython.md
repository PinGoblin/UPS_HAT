# MicroPython notes

- The library imports about 100 KB of RAM on a 64-bit build, and roughly half that on 32-bit boards. RP2040, RP2350 and ESP32 boards are suitable. On smaller boards, use `.mpy` files or freeze the package into the firmware.
- Docstrings are discarded when MicroPython compiles the code, so they cost no RAM. They do take flash space in the `.py` files; `.mpy` files leave them out.
- `vcgencmd` monitoring is not available on MicroPython. Pass `pi_monitor=False`.
- `state_file` works on boards with a filesystem, but flash wears with frequent writes. The library saves at most every 5 minutes.

Example (`examples/micropython_main.py`):

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
