# PinGoblin UPS HAT+ Library

The `ups_hat` library reads and controls everything the PinGoblin UPS HAT+ can measure, control or report. The same code runs on a Raspberry Pi (Python 3.7 or later) and on MicroPython boards such as the Raspberry Pi Pico and ESP32. It needs no third-party packages.

The library talks to two chips on the PinGoblin UPS HAT+ I²C bus:

| Chip | Function | Address |
|---|---|---|
| BQ25798 | Charger, power path, measurements, ship mode | 0x6B |
| STUSB4500 | USB-C PD controller | 0x28 |

The UPS Pack and the 5.1 V output stage have no I²C connection. The library works out their state from the charger's measurements and reports their faults with the source `inferred`.

!!! warning "USB-C adapter"
    Use a USB PD adapter that offers 9 V or 15 V at 3 A. A 5 V-only adapter is not supported: The library reports `PD_NO_CONTRACT` or `PD_LOW_CONTRACT`.

## Quick start

```python
from ups_hat import UPS, UPSError

try:
    ups = UPS(cells_parallel=1, cell_capacity_mah=3000)   # Raspberry Pi
    s = ups.poll()
except (UPSError, OSError) as e:
    raise SystemExit("UPS HAT+ not available: %s" % e)

print(s.vbat, s.ibat, s.soc, s.on_battery)
print(s.fault_codes())
print(ups.report(s))
```

To act on faults as they happen:

```python
@ups.on_fault
def alert(fault):
    print(fault)            # [WARNING] BAT_HIGH_RESISTANCE: Battery path resistance is high. (ohm=0.41)

ups.run(interval_s=2)       # poll forever
```

## Where next

- [Installation](guide/install.md): Raspberry Pi OS or MicroPython.
- [Concepts](guide/concepts.md): Polling, units, state of charge and the settings the library enforces.
- [Power-off integration](guide/power-off.md): The service and shutdown hook that shut the Pi down at low battery.
- [Safety and limits](guide/safety.md): Limits the library enforces, and calls that can cause damage.
- [Fault codes](faults.md): Every fault, its meaning and what to do.
- [API reference](reference/ups.md): Every class, method and property.
