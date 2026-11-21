# ups_hat: UPS HAT+ library for Python and MicroPython

`ups_hat` gives software access to everything the UPS HAT+ can measure, control or report. The same code runs on a Raspberry Pi (CPython 3.7 or later) and on MicroPython boards. It needs no third-party packages.

The library talks to two chips on the HAT's I²C bus. The Pi's header I²C is bus 1, on pins 3 and 5.

| Chip | Function | Address |
|---|---|---|
| BQ25798 (U2) | Charger, power path, ADC, ship mode | 0x6B |
| STUSB4500 (U1) | USB-C PD sink controller | 0x28 |

The battery pack board (protector, balancer, fuse) and the HAT's 5.1 V converter (U6, TPS54620 buck) have no I²C interface. The library works out their state from the measurements instead; these faults are marked `inferred` in the tables below. Rev D has no battery temperature sensor: R4/R5 hold the charger's TS input at 60 % of REGN (normal temperature), and the library reports `BOARD_TS_FAULT` if that reading leaves 50–70 %.

The USB-C adapter must offer USB PD at 9 V or 15 V, 3 A. A 5 V-only adapter runs a lightly loaded Pi but is not supported; the library reports `PD_LOW_CONTRACT` or `PD_NO_CONTRACT`.

Full documentation, including the API reference, is built with MkDocs from the `docs/` folder:

```sh
pip install -r requirements-docs.txt
mkdocs serve        # preview at http://127.0.0.1:8000
```

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Concepts](#concepts)
- [`UPS` reference](#ups-reference)
- [`Snapshot` fields](#snapshot-fields)
- [Fault codes](#fault-codes)
- [Low-level drivers](#low-level-drivers)
- [Power-off integration on Raspberry Pi OS](#power-off-integration-on-raspberry-pi-os)
- [MicroPython notes](#micropython-notes)
- [Releases](#releases)
- [Safety and limits](#safety-and-limits)
- [Version 1.4.0](#version-140)
- [Testing without hardware](#testing-without-hardware)
- [Licence](#licence)

## Installation

### Raspberry Pi

1. Enable I²C: `sudo raspi-config` → Interface Options → I2C. Alternatively, add `dtparam=i2c_arm=on` to `/boot/firmware/config.txt`.
2. Install the library:

```sh
sudo pip install git+https://github.com/PinGoblin/UPS_HAT   # add --break-system-packages on Bookworm
ups-hat status                                              # or: python3 -m ups_hat.cli status
```

The library opens `/dev/i2c-1` by itself. Run it as root, or add your user to the `i2c` group.

### MicroPython

Recommended: download `ups_hat-mpy-<version>.zip` from the [latest release](https://github.com/PinGoblin/UPS_HAT/releases/latest), unzip it and copy the folder to the board:

```sh
mpremote cp -r ups_hat :
```

Or install the source files with `mip`:

```sh
mpremote mip install github:PinGoblin/UPS_HAT/micropython
```

The `.mpy` files need about 90 KB of free heap on a 32-bit board, the `.py` files about 130 KB (measured in CI; see the MicroPython notes in the documentation). The command-line tool and Pi 5 monitoring are Raspberry Pi only.

## Quick start

```python
from ups_hat import UPS

ups = UPS(cells_parallel=1, cell_capacity_mah=3000)   # Raspberry Pi
s = ups.poll()
print(s.vbat, s.ibat, s.soc, s.on_battery)
print(s.fault_codes())
print(ups.report(s))
```

On MicroPython, pass your I²C object:

```python
from machine import I2C, Pin
from ups_hat import UPS
ups = UPS(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000), pi_monitor=False)
```

To receive events:

```python
@ups.on_fault
def alert(fault):
    print(fault)            # [WARNING] BAT_HIGH_RESISTANCE: Battery path resistance is high. (ohm=0.41)

ups.run(interval_s=2)       # poll forever
```

## Concepts

**Polling.** Call `poll()` every 1–5 s. Each call does four things:
- Reads the charger ADC, status, faults and latched flags, plus the USB-C status and contract.
- Updates the battery model.
- Re-applies the charger settings if the charger has reset.
- Evaluates every fault rule and returns a `Snapshot`.

The charger's interrupt pin is not wired, so the library reads the latched flag registers on every poll. That way it still catches a fault that appeared and cleared between two polls. Such a fault is reported once, with `transient=True`.

**Units.** Volts, amps, watts, °C, mAh, percent and hours. For battery current, a positive value means charging and a negative value means discharging.

**State of charge.**
- SoC is counted from the battery current.
- It is set to 100 % when the charger reports *charge done*.
- It is corrected from the resting voltage after 30 minutes with no load.
- 100 % means full at the configured charge voltage (8.20 V by default), so capacities are usable capacities.
- Capacity is learned automatically after a deep discharge from full.
- Battery-path resistance is learned from load steps.
- Give a `state_file` to keep what has been learned between runs.

**Fault sources.**
- `charger`: read from the BQ25798.
- `pd`: read from the STUSB4500.
- `bus`: a chip did not answer.
- `pi`: read from the Raspberry Pi 5 firmware with `vcgencmd`.
- `inferred`: worked out from measurements over time. Treat an inferred fault as a strong hint rather than proof. Most inferred faults must persist for a few seconds to a few minutes before they are reported.

**Settings the library enforces** (`auto_configure=True`):
- Charger I²C watchdog off, so the settings hold.
- Charge voltage and charge current as configured.
- ADC on at 15 bits.
- Discharge-current sensing on, so the battery current is valid on battery power.
- `SFET_PRESENT` set, which unlocks ship mode and the SW1 wake-up.

The library checks these every minute and re-applies them after a charger reset. When it does, it reports `CHG_RESET_DETECTED`. On every change of USB-C contract, it sets the charger input current limit from the contract.

**Hardware cut-off.** If no software acts, the HAT's 5.1 V output switches off when the pack falls to about 5.6 V (2.8 V per cell) and back on above about 6.1 V. The library's own shutdown (5 % SoC or 6.2 V under load) comes first.

## `UPS` reference

```python
UPS(i2c=None, cells_parallel=1, cell_capacity_mah=3000.0, charge_voltage=8.2,
    charge_current=None, ship_fet=True, state_file=None, low_battery_soc=5.0,
    low_battery_voltage=6.2, auto_configure=True, protect=True, pi_monitor=True, bus=1)
```

| Argument | Meaning |
|---|---|
| `i2c` | An object with MicroPython `machine.I2C` memory methods. Defaults to `/dev/i2c-<bus>` on Linux. |
| `cells_parallel` | 1 = 2S1P (two cells), 2 = 2S2P (four cells). |
| `cell_capacity_mah` | Rated capacity of one cell. |
| `charge_voltage` | Pack charge voltage. Limited to 7.0–8.4 V. 8.2 V (4.10 V per cell) gives long life. |
| `charge_current` | Defaults to 1.5 A (2S1P) or 2.0 A (2S2P). Limited to 3.0 A. |
| `ship_fet` | True when the board has the SDRV ship FET fitted. Needed for `power_off()` and ship mode. |
| `state_file` | JSON file for learned battery data and shutdown history. |
| `low_battery_soc`, `low_battery_voltage` | On battery, `should_shutdown` becomes True when the SoC falls to this value or the voltage falls to this value. |
| `auto_configure` | Apply and maintain the charger settings. |
| `protect` | Stop charging on a battery wiring fault, and resume when it clears. |
| `pi_monitor` | Read the Pi 5 supply state with `vcgencmd` when available. |

### Methods

| Method | What it does |
|---|---|
| `poll()` | Read and diagnose everything. Returns a `Snapshot`. |
| `run(interval_s=2, callback=None, count=None)` | Poll repeatedly, calling `callback(snapshot)` each time. |
| `report(snapshot=None)` | Multi-line human-readable status. |
| `on_fault(fn)`, `on_clear(fn)` | Register callbacks for new and cleared faults. Usable as decorators. |
| `faults` | Faults active after the last poll. |
| `acknowledge(code)` | Clear a latched inferred fault: `BAT_EARLY_CUTOFF`, `BAT_IMBALANCE_SUSPECTED`, `BAT_SELF_DISCHARGE` or `CHG_RESET_DETECTED`. |
| `new_cells_fitted()` | Forget learned capacity, resistance and history after fitting new cells. |
| `configure()` | Re-apply all charger settings. |
| `enable_charging(on=True)`, `charging_enabled` | Turn charging on or off, or read whether it is on. |
| `set_charge_voltage(v)`, `set_charge_current(a)`, `set_input_current_limit(a)` | Change the limits. Values are clamped to the board limits. |
| `sync_input_current_limit()` | Set the input current limit from the PD contract, or from the USB-C Rp advertisement when there is no PD contract. |
| `power_off(low_battery=None)` | Final shutdown step: returns `"ship"`, `"reset"` or `"none"`. See [Power-off integration](#power-off-integration-on-raspberry-pi-os). |
| `ship_mode(delay=False)` | Disconnect the battery. The board wakes on SW1 or when an adapter is plugged in. The charger ignores this while an adapter is connected. |
| `shutdown_mode(delay=False)` | Lowest-drain off state. Only plugging in an adapter wakes the board. |
| `system_reset(delay=False)` | Power-cycle the Pi. |
| `renegotiate_pd()` | Send a USB PD soft reset so the adapter re-offers its voltages. |
| `pd_config()` | Sink PDOs in RAM and in NVM. |
| `check_pd_config()` | True when the PDOs match the factory set: 5 V / 3 A, 9 V / 3 A and 15 V / 3 A. |
| `restore_pd_defaults(write_nvm=False)` | Reload the factory PDOs. Pass `write_nvm=True` to also reprogram the NVM (service use only). |
| `save_state(clean=False)` | Write `state_file`. Pass `clean=True` on a normal shutdown. |
| `charger`, `pd`, `battery`, `pi` | The underlying `BQ25798`, `STUSB4500`, `BatteryMonitor` and `PiPower` objects. |

## `Snapshot` fields

| Field | Meaning |
|---|---|
| `time`, `wall_time` | Monotonic seconds, and epoch seconds (None if the clock is not set). |
| `charger_ok`, `pd_ok` | Whether each chip answered. |
| `vbus`, `ibus` | USB-C input voltage (V) and current (A). |
| `vbat`, `ibat` | Battery voltage (V) and current (A, positive when charging). |
| `vsys` | System rail feeding the 5.1 V converter (V). |
| `tdie` | Charger die temperature (°C). |
| `ts_pct` | Charger TS input as % of REGN. Fixed at about 60 % by R4/R5 (no NTC); outside 50–70 % raises `BOARD_TS_FAULT`. |
| `adapter_present`, `power_good`, `on_battery` | Input state. `on_battery` means the board is running from the cells. |
| `charging`, `charge_state`, `charge_state_text` | Charging phase: not charging, trickle, pre-charge, fast (CC), taper (CV), top-off or done. |
| `battery_present` | A battery is detected. |
| `soc`, `remaining_mah`, `capacity_mah` | State of charge (%), remaining charge (mAh) and capacity (mAh, learned or rated). |
| `time_to_empty_h`, `time_to_full_h` | Estimates at the present current. |
| `battery_resistance` | Battery-path resistance (Ω): cells, holders, wiring, fuse and protection FETs. |
| `input_power`, `battery_power`, `output_power` | Power in watts. `battery_power` is positive when the battery supplies power. `output_power` is an estimate of the 5.1 V output. |
| `contract_voltage`, `contract_current` | The USB PD contract, or None. |
| `status`, `charger_faults`, `flags` | Raw decoded charger status, active faults and latched flags. |
| `pd` | USB-C status: attach state, CC levels, orientation, policy-engine state, contract and events. |
| `pi` | `{"throttled": {...}, "ext5v": volts}` on a Pi 5, otherwise empty. |
| `faults`, `new_faults`, `cleared_faults` | `Fault` objects, sorted with the most severe first. |
| `should_shutdown` | The battery is critically low. Shut the Pi down now. |
| `fault_codes()`, `worst_severity()`, `to_dict()` | Helper methods. |

A `Fault` object has the attributes `code`, `severity` (0 = info, 1 = warning, 2 = critical), `severity_name`, `source`, `message`, `advice`, `data`, `transient` and `since`.

## Fault codes

| Code | Severity | Source | Meaning | What to do |
|---|---|---|---|---|
| `BUS_CHARGER_MISSING` | critical | bus | Charger (BQ25798, 0x6B) is not answering on I2C. | Check that I2C is enabled and the HAT is seated. If it persists the charger may be damaged. |
| `BUS_PD_MISSING` | warning | bus | USB-C controller (STUSB4500, 0x28) is not answering on I2C. | Power is unaffected but PD information is unavailable. Re-seat the HAT. |
| `CHG_CONVERTER_OCP` | critical | charger | Charger converter over-current. | Possible board fault or short on SYS. |
| `CHG_IBAT_OCP` | critical | charger | Battery over-current. | Check for a short or a damaged cell; check battery wiring. |
| `CHG_IBAT_REGULATION` | info | charger | Battery discharge current is being limited. | — |
| `CHG_IBUS_OCP` | warning | charger | Input over-current. | The load is above what the adapter can supply. |
| `CHG_INPUT_LIMITED` | info | charger | Adapter is at its current or voltage limit. | Use a USB-C PD adapter that offers 9 V or 15 V at 3 A (15 V for full load while charging). |
| `CHG_POOR_SOURCE` | warning | charger | Weak adapter detected. | Use a USB-C PD adapter that offers 9 V or 15 V at 3 A, and a good cable. |
| `CHG_PRECHARGE_TIMER_EXPIRED` | warning | charger | Pre-charge timer expired: the battery did not recover from deep discharge. | A cell is probably damaged. Replace both cells. |
| `CHG_RESET_DETECTED` | warning | charger | Charger settings had returned to defaults (power-on reset). | The charger lost power: pack disconnected, pack protection tripped or SYS brown-out. Settings re-applied. |
| `CHG_THERMAL_REGULATION` | info | charger | Charger is reducing current to limit its temperature. | Improve airflow. |
| `CHG_THERMAL_SHUTDOWN` | critical | charger | Charger thermal shutdown. | Improve airflow; reduce load or charge current. |
| `CHG_TIMER_EXPIRED` | warning | charger | Fast-charge safety timer expired before the battery was full. | The cells may be worn, or the charge current is too low for their capacity (check cells_parallel). |
| `CHG_TRICKLE_TIMER_EXPIRED` | warning | charger | Trickle-charge timer expired: the battery voltage stayed very low. | Check the pack cable; a cell may be dead or the pack fuse blown. |
| `CHG_VAC_OVP` | critical | charger | Input (VAC) over-voltage. | Unplug the adapter; it is faulty or not USB-C PD compliant. |
| `CHG_VBAT_OVP` | critical | charger | Battery over-voltage. | Check the cells are Li-ion 3.6/3.7 V types wired as 2S. Charging is stopped. |
| `CHG_VBUS_OVP` | critical | charger | USB-C input over-voltage. | Unplug the adapter; it is faulty or not USB-C PD compliant. |
| `CHG_VSYS_OVP` | critical | charger | System rail (SYS) over-voltage. | Board fault; disconnect power. |
| `CHG_VSYS_SHORT` | critical | charger | System rail (SYS) short circuit. | Remove the Pi and accessories; if it persists the board is faulty. |
| `CHG_WATCHDOG_EXPIRED` | warning | charger | Charger I2C watchdog expired; charger settings returned to defaults. | The library re-applies its settings automatically. |
| `PD_CAPABILITY_MISMATCH` | warning | pd | Adapter cannot supply the current requested. | Use a PD adapter that offers 9 V or 15 V at 3 A. |
| `PD_CC_OVERVOLTAGE` | critical | pd | Over-voltage on the USB-C CC lines. | Unplug the cable; it or the adapter is faulty. |
| `PD_CONFIG_MISMATCH` | warning | pd | USB-C controller PDO settings differ from the factory settings. | Run UPS.restore_pd_defaults() or contact support. |
| `PD_LOW_CONTRACT` | info | pd | Adapter offered less than 9 V. | Use a PD adapter that offers 9 V or 15 V at 3 A. |
| `PD_NO_CONTRACT` | info | pd | Adapter is not USB PD (5 V only). | Not supported: the Pi gets about 11 W at most and charging is slow. Use a USB-C PD adapter that offers 9 V or 15 V at 3 A. |
| `ADAPTER_INSUFFICIENT` | warning | inferred | Running partly from battery while the adapter is connected. | The adapter cannot carry the load. Use a USB-C PD adapter that offers 15 V at 3 A. |
| `BAT_ABSENT` | critical | inferred | No battery detected. | Plug the pack's XT30 lead into J3, switch the pack ON and check its cells are fitted. A pack that is switched off, has tripped its protection or temperature cut-off, or has a blown fuse also reads as absent. |
| `BAT_CAPACITY_LOW` | warning | inferred | Measured battery capacity is well below the rated capacity. | The cells are worn, or cell_capacity_mah is set too high. |
| `BAT_CHARGE_BLOCKED` | warning | inferred | Charging has stopped before the battery is full. | The pack's protection (HY2120) has blocked charging: one cell reached 4.25 V, so the cells are out of balance. Check the cells in the pack. |
| `BAT_CRITICAL` | critical | inferred | Battery critically low; shut down now. | Connect the adapter. |
| `BAT_DEEPLY_DISCHARGED` | warning | inferred | Battery is below 6.0 V (deeply discharged). | Leave on the adapter; if it does not recover within an hour replace both cells. |
| `BAT_EARLY_CUTOFF` | warning | inferred | Power was lost on battery while the pack still had charge. | One cell may be weak, or the load exceeded the pack's protection limit. Check the cells. |
| `BAT_HIGH_RESISTANCE` | warning | inferred | Battery path resistance is high. | Clean the pack's cell contacts and check the pack cable and connectors. A gradual rise means the cells are ageing. |
| `BAT_IMBALANCE_SUSPECTED` | warning | inferred | Cells appear to be out of balance. | Charging repeatedly stops early. Balancing will correct small differences over several charges; replace both cells with a matched pair if it persists. |
| `BAT_LOW` | warning | inferred | Battery low. | Connect the adapter. |
| `BAT_PARALLEL_CELL_MISSING` | warning | inferred | Configured for 2S2P but the battery behaves like 2S1P. | Check that all four cells are fitted, or set cells_parallel=1. |
| `BAT_SELF_DISCHARGE` | warning | inferred | Battery needs recharging unusually often while on the adapter. | A cell may be leaking charge. Replace both cells if it persists. |
| `BAT_WIRING_FAULT` | critical | inferred | Battery reads like a single cell or a reversed cell. | Check both cells in the pack are fitted the right way round. Charging is stopped. |
| `BOARD_TS_FAULT` | warning | inferred | Charger TS input is out of range; charging is blocked. | R4/R5 (TS divider, 60 % of REGN) are damaged or missing. Return the board for repair. |
| `BOARD_HOT` | warning | inferred | Charger temperature is high. | Improve airflow around the HAT. |
| `BOARD_OVERHEAT` | critical | inferred | Charger temperature is very high. | Shut down and improve cooling. |
| `CABLE_RESISTANCE_HIGH` | warning | inferred | High voltage drop in the USB-C cable or connector. | Use a shorter or better USB-C cable (rated 3 A or 5 A). |
| `OUTPUT_5V_FAULT` | critical | inferred | 5 V output is low while the battery/adapter rail is healthy. | The 5.1 V stage is current limiting or faulty, or the Pi is drawing more than 5 A. |
| `OUTPUT_OVERLOAD` | warning | inferred | Output power is near the 25 W limit. | Reduce the load on the Pi and its USB ports. |
| `PI_EXTERNAL_SUPPLY` | info | inferred | The Pi appears to be powered from its own USB-C supply. | The UPS is not carrying the load. Remove the Pi's own supply to get battery backup. |
| `PI_UNDERVOLTAGE` | warning | pi | The Pi reports under-voltage on its 5 V input. | Reduce load; if SYS is healthy the 5.1 V stage is current limiting. |
| `PI_UNDERVOLTAGE_OCCURRED` | info | pi | The Pi has seen under-voltage since boot. | — |

## Low-level drivers

Use the low-level drivers directly when you need register access.

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

**`BQ25798`** exposes the following settings as properties:
- Minimum system voltage, charge voltage and current, input voltage and current limits.
- Pre-charge current and threshold, termination current, recharge offset and deglitch.
- All charge timers.
- Charge enable, ICO, HiZ, termination enable, auto/forced battery discharge, VAC OVP and the watchdog.
- Input detection, ship-FET control, PFM/OOA, the STAT pin, VSYS short protection and IBUS OCP.
- `SFET_PRESENT`, discharge-current sensing (`EN_IBAT`), IINDPM/ILIM enables and battery OCP.
- Thermal regulation and shutdown thresholds, and the VBUS pull-down.

It also provides these methods:
- `status()`, `faults()`, `read_flags()`.
- `read_adc()`, `adc_enable()`.
- `part_information()`, `dump()`, `reset_registers()`.
- `field()` and `set_field()` for anything else.

The driver deliberately offers no way to turn on OTG, ACFET/RBFET or MPPT. `ts_ignore` (REG0x18 bit 0) is exposed but not used: the TS divider already reads as normal temperature. OTG would drive voltage back into the USB-C port, which is sink-only.

**`STUSB4500`** provides:
- `status()`, `monitoring_events()`, `contract`, `pe_state`.
- `sink_pdos()`, `set_sink_pdo()`, `pdo_count`.
- `renegotiate()`, `software_reset()`, `clear_alerts()`.
- `read_nvm()` and `write_nvm(sectors, confirm=True)`.
- `decode_nvm_pdos()` and `encode_nvm_pdos()`.

The NVM has limited write endurance, so it is programmed once in the factory test jig. Writing it needs `confirm=True`.

**`BatteryMonitor`** is the SoC, capacity and resistance model. It can be used on its own.

**`PiPower`** reads `vcgencmd get_throttled` and `vcgencmd pmic_read_adc EXT5V_V` (Pi 5).

## Power-off integration on Raspberry Pi OS

1. Install the library.
2. Copy `examples/` to `/usr/local/lib/ups-hat/examples/`.
3. Install the service and the shutdown hook, then start the service:

```sh
sudo cp examples/systemd/ups-hat.service /etc/systemd/system/
sudo cp examples/systemd/ups-hat-shutdown /usr/lib/systemd/system-shutdown/
sudo systemctl enable --now ups-hat
```

**The daemon** (`examples/pi_daemon.py`):
- Polls every 2 s and logs faults to the journal (`journalctl -u ups-hat`).
- Writes `/run/ups-hat/status.json`.
- At low battery, creates `/run/ups-lowbatt` and runs `systemctl poweroff`.

**The shutdown hook** runs as the very last step of a power-off or halt. It never acts on a reboot. It calls `power_off()`, which does one of three things:

| Situation | Action |
|---|---|
| No adapter | Ship mode. The board goes dark. Press SW1 or plug in an adapter to start again. |
| Adapter connected, low-battery shutdown | System reset, so the Pi boots on mains instead of sitting halted. |
| Adapter connected, user shutdown | Nothing. The Pi halts and the board stays on. |

Edit the `Environment=` lines in `ups-hat.service` to match your cells.

## MicroPython notes

- RAM use, measured on MicroPython v1.25.0 (32-bit unix port): about 72 KB while running, and a heap of at least 90 KB with `.mpy` files or 130 KB with `.py` files (which the board must compile). Check yours with `gc.mem_free()` before importing.
- Docstrings are discarded when MicroPython compiles the code, so they cost no RAM.
- `vcgencmd` monitoring is not available on MicroPython. Pass `pi_monitor=False`.
- `state_file` works on boards with a filesystem, but flash wears with frequent writes. The library saves at most every 5 minutes.

## Releases

Push a tag such as `v1.5.0` (after setting that version in `pyproject.toml`, `ups_hat/__init__.py` and `micropython/package.json`; `python3 tools/check_packaging.py v1.5.0` checks them). GitHub then builds the `.mpy` files and publishes a release with `ups_hat-mpy-1.5.0.zip` attached.

## Safety and limits

- The charge voltage is clamped to 7.0–8.4 V, the charge current to 3.0 A and the input current limit to 3.0 A.
- The USB-C adapter must offer USB PD at 9 V or 15 V, 3 A. With 9 V the adapter covers about 22 W of Pi load; above that, and with any 5 V source, the pack makes up the difference.
- `power_off()`, `ship_mode()`, `shutdown_mode()` and `system_reset()` need the SDRV ship FET. On a board built without it, pass `ship_fet=False`; these calls then raise `NotSupported`.
- `BAT_WIRING_FAULT` stops charging while the pack reads like a single or reversed cell (2.5–4.6 V). Charging resumes when the reading is normal again.
- Inferred battery faults are estimates. Confirm them by measuring the cells before replacing anything.

## Version 1.4.0

The main class is `UPS` and the base error class is `UPSError`. Code written for 1.3 needs those two names changed; nothing else in the interface changed.

## Testing without hardware

`tests/sim.py` simulates both chips at register level. Run the tests with either interpreter:

```sh
python3 tests/test_ups_hat.py
micropython tests/test_ups_hat.py
```

## Licence

MIT. See [LICENSE](LICENSE).
