# Concepts

## Polling

Call [`poll()`][ups_hat.board.UPS.poll] every 1–5 s. Each call:

- reads the charger ADC, status, faults and latched flags, plus the USB-C status and contract;
- updates the battery model;
- re-applies the charger settings if the charger has reset;
- evaluates every fault rule and returns a [`Snapshot`][ups_hat.board.Snapshot].

This library reads the chargers latched flag registers on every poll. Faults that appear briefly but are cleared between polls will be captured and reported once, with `transient=True`.

## Units

Volts, amps, watts, °C, mAh, percent and hours. For battery current, a positive value means charging and a negative value means discharging.

## State of charge

- SoC is calculated from the battery current.
- It is set to 100 % when the charger reports *charge done*.
- It is corrected from the resting voltage after 30 minutes with no load.
- 100 % means full at the configured charge voltage (8.20 V by default), so capacities are usable capacities.
- Capacity is learned automatically after a deep discharge from full.
- Similarly, battery-path resistance is learned from load steps.
- A `state_file` keeps what has been learned between runs.

## Fault sources

| Source | Meaning |
|---|---|
| `charger` | Read from the BQ25798. |
| `pd` | Read from the STUSB4500. |
| `bus` | A chip did not answer. |
| `pi` | Read from the Raspberry Pi 5 firmware with `vcgencmd`. |
| `inferred` | Worked out from measurements over time. A strong hint rather than proof; most must persist for a few seconds to a few minutes before they are reported. |

## Settings the library enforces

With `auto_configure=True`:

- charger I²C watchdog off, so the settings hold;
- charge voltage and charge current as configured;
- ADC on at 15 bits;
- discharge-current sensing on, so the battery current is valid on battery power;
- `SFET_PRESENT` set, which unlocks ship mode and the SW1 wake-up.

The library checks these every minute and re-applies them after a charger reset. When it does, it reports `CHG_RESET_DETECTED`. On every change of USB-C contract, it sets the charger input current limit from the contract.

## Hardware cut-off

If no software acts, the HAT's 5.1 V output switches off when the pack falls to about 5.6 V (2.8 V per cell) and back on above about 6.1 V. If running, the library's own shutdown will occur earlier as it is set to 5 % SoC or 6.2 V under load, whichever comes first.

## Low-level drivers

Use the drivers directly when you need register access:

```python
from ups_hat import BQ25798, STUSB4500, LinuxI2C

i2c = LinuxI2C(1)
chg = BQ25798(i2c)
print(chg.read_adc())                 # ADCReading(vbus=..., ibus=..., vbat=...)
print(chg.status()["charge_state_text"], chg.faults(), chg.read_flags())
chg.charge_current = 1.0
print(hex(chg.dump()[0x1C]))

pd = STUSB4500(i2c)
print(pd.status(), pd.contract, pd.sink_pdos())
```

The BQ25798 driver deliberately offers no way to turn on OTG, ACFET/RBFET or MPPT: OTG would drive voltage back into the USB-C port, which is sink-only. The STUSB4500 NVM has limited write endurance, so it is programmed once in the factory test jig and writing it needs `confirm=True`.
