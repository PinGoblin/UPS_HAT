# Fault codes

These fault codes are listed in [`CATALOGUE`][ups_hat.faults.CATALOGUE] and have the following attributes:

- **Severity:** `info` needs no action, `warning` needs attention, `critical` needs action now.
- **Source:** `charger` and `pd` faults are read from the chips; `bus` means a chip did not answer; `pi` comes from the Raspberry Pi 5 firmware; `inferred` faults are calculated indirectly from measurements over time. Most inferred faults are strong hints rather than proof of a fault, and must persist for a few seconds to a few minutes before they are reported.

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
| `BOARD_HOT` | warning | inferred | Charger temperature is high. | Improve airflow around the HAT. |
| `BOARD_OVERHEAT` | critical | inferred | Charger temperature is very high. | Shut down and improve cooling. |
| `BOARD_TS_FAULT` | warning | inferred | Charger TS input is out of range; charging is blocked. | R4/R5 (TS divider, 60 % of REGN) are damaged or missing. Return the board for repair. |
| `CABLE_RESISTANCE_HIGH` | warning | inferred | High voltage drop in the USB-C cable or connector. | Use a shorter or better USB-C cable (rated 3 A or 5 A). |
| `OUTPUT_5V_FAULT` | critical | inferred | 5 V output is low while the battery/adapter rail is healthy. | The 5.1 V stage is current limiting or faulty, or the Pi is drawing more than 5 A. |
| `OUTPUT_OVERLOAD` | warning | inferred | Output power is near the 25 W limit. | Reduce the load on the Pi and its USB ports. |
| `PI_EXTERNAL_SUPPLY` | info | inferred | The Pi appears to be powered from its own USB-C supply. | The UPS is not carrying the load. Remove the Pi's own supply to get battery backup. |
| `PI_UNDERVOLTAGE` | warning | pi | The Pi reports under-voltage on its 5 V input. | Reduce load; if SYS is healthy the 5.1 V stage is current limiting. |
| `PI_UNDERVOLTAGE_OCCURRED` | info | pi | The Pi has seen under-voltage since boot. | — |
