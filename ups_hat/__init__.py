"""UPS HAT+ for Raspberry Pi: Python and MicroPython library.

The package re-exports everything most programs need, so `from ups_hat import UPS`
is enough for normal use.

Example: Raspberry Pi
    ```python
    from ups_hat import UPS

    ups = UPS(cells_parallel=1, cell_capacity_mah=3000)
    print(ups.report())
    ```

Example: MicroPython
    ```python
    from machine import I2C, Pin
    from ups_hat import UPS

    ups = UPS(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000), pi_monitor=False)
    s = ups.poll()
    print(s.vbat, s.soc, s.fault_codes())
    ```
"""

from .board import UPS, Snapshot, FACTORY_PDOS
from .bq25798 import BQ25798, ADCReading
from .stusb4500 import STUSB4500, PDO, Contract
from .battery import BatteryMonitor
from .faults import Fault, CATALOGUE, INFO, WARNING, CRITICAL
from .bus import (UPSError, DeviceNotFound, BusError, NotSupported, LinuxI2C,
                  I2CDevice, open_bus)

__version__ = "1.4.0"
