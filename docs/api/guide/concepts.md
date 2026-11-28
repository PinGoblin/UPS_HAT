# Concepts

## Polling

Call [`poll()`][ups_hat.board.UPS.poll] every 1–5 s. Each call:

- Reads the charger's measurements, status, faults and latched flags, and the USB-C status and contract.
- Updates the battery model.
- Re-applies the charger settings if the charger has reset.
- Checks every fault rule and returns a [`Snapshot`][ups_hat.board.Snapshot].

A fault that appears and clears between two polls is still caught from the charger's latched flags. It is reported once, with `transient=True`.

## Units

| Quantity | Unit |
|---|---|
| Voltage | V |
| Current | A (battery current: positive when charging, negative when discharging) |
| Power | W |
| Temperature | °C |
| Charge | mAh |
| State of charge | % |
| Time to empty or full | hours |

## State of charge

- The state of charge (SoC) is counted from the battery current.
- It is set to 100 % when the charger reports *charge done*.
- It is corrected from the resting voltage after 30 minutes with no load.
- 100 % means full at the configured charge voltage (8.20 V by default), so the reported capacity is the usable capacity.
- The capacity is learned after a deep discharge from full, and the battery-path resistance is learned from load steps.
- Pass a `state_file` to keep what has been learned between runs.

## Fault sources

| Source | Meaning |
|---|---|
| `charger` | Read from the BQ25798. |
| `pd` | Read from the STUSB4500. |
| `bus` | A chip did not answer. |
| `pi` | Read from the Raspberry Pi 5 firmware with `vcgencmd`. |
| `inferred` | Worked out from measurements over time. Most must hold for 5 s to 2 minutes before they are reported. Confirm an inferred battery fault by measuring the cells before replacing anything. |

## Settings the library enforces

With `auto_configure=True`, the library sets:

- The charger I²C watchdog off, so the settings hold.
- The charge voltage and charge current you configured.
- The measurement ADC on, at 15 bits.
- Discharge-current measurement on, so the battery current is valid on battery power.
- `SFET_PRESENT`, which enables ship mode and the SW1 wake-up.

It checks these every minute and re-applies them after a charger reset, reporting `CHG_RESET_DETECTED` when it does. On every change of USB-C contract, it sets the charger's input current limit to suit the contract.

## Low-battery shutdown

| Level | Action |
|---|---|
| 5 % SoC, or 6.2 V under load | The library sets `should_shutdown`. The [power-off integration](power-off.md) shuts the Pi down. |
| 5.6 V (2.8 V per cell) | The PinGoblin UPS HAT+ switches its 5.1 V output off, whether or not software is running. It switches back on above 6.1 V. |

Change the first level with `low_battery_soc` and `low_battery_voltage`.

## Low-level drivers

Use the chip drivers directly for register access:

```python
from ups_hat import BQ25798, STUSB4500, LinuxI2C

with LinuxI2C(1) as i2c:
    chg = BQ25798(i2c)
    print(chg.read_adc())                 # ADCReading(vbus=..., ibus=..., vbat=...)
    print(chg.status()["charge_state_text"], chg.faults(), chg.read_flags())
    print(hex(chg.dump()[0x1C]))

    pd = STUSB4500(i2c)
    print(pd.status(), pd.contract, pd.sink_pdos())
```

The BQ25798 driver has no way to turn on OTG, ACFET/RBFET or MPPT. OTG would drive voltage back into the USB-C port, which is sink-only.

!!! danger "Settings written through the drivers"
    The drivers accept any value in the chip's own range, for example a charge voltage up to 18.8 V. A charge voltage or charge current that does not suit the UPS Pack can over-charge or damage the cells. Use the [`UPS`][ups_hat.board.UPS] methods, which clamp every value to the board's limits, unless you need a register the `UPS` class does not cover.
