# PinGoblin UPS HAT+ Library

The `ups_hat` library provides access to everything the PinGoblin UPS HAT+ can measure, control or report. This code will run on CPython / Micropython compatible boards such as the Raspberry Pi, Arduino, and ESP32 and needs no third-party packages.

The library talks to the below IC's on the USB HAT's I²C bus. 

| Chip | Function | Address |
|---|---|---|
| BQ25798 (U2) | Charger, power path, ADC, ship mode | 0x6B |
| STUSB4500 (U1) | USB-C PD sink controller | 0x28 |

Components such as connected battery packs and the HAT's 5.1 V converter (TPS54620 buck) do not have an I²C interface. This library works out their state from indirect measurements. Where an indirect measurement has been made, and results in a fault conditionl, the fault will be reported as `inferred`. Rev D has no battery temperature sensor: R4/R5 hold the charger's TS input at 60 % of REGN (normal temperature), and the library reports `BOARD_TS_FAULT` if that reading leaves 50–70 %. All PinGolbin battery packs contain temperature sensing, high-temperature charging cut-offs, over/under charge cut-offs and cell balancing.

!!! note "USB-C adapter"
    The adapter must offer USB PD at 9 V or 15 V, 3 A. A 5 V-only adapter will run a lightly loaded Pi but is not supported (the library will report `PD_LOW_CONTRACT` or `PD_NO_CONTRACT`).

## Quick start

```python
from ups_hat import UPS

ups = UPS(cells_parallel=1, cell_capacity_mah=3000)   # Raspberry Pi
s = ups.poll()
print(s.vbat, s.ibat, s.soc, s.on_battery)
print(s.fault_codes())
print(ups.report(s))
```

To receive events:

```python
@ups.on_fault
def alert(fault):
    print(fault)            # [WARNING] BAT_HIGH_RESISTANCE: Battery path resistance is high. (ohm=0.41)

ups.run(interval_s=2)       # poll forever
```

## Where next

- [Installation](guide/install.md) on Raspberry Pi OS or MicroPython.
- [Concepts](guide/concepts.md): polling, units, state of charge and the settings the library enforces.
- [Power-off integration](guide/power-off.md): the daemon, systemd service and shutdown hook.
- [Fault codes](faults.md): every fault, its meaning and what to do.
- [API reference](reference/ups.md): every class, method and property.
