# Troubleshooting

| Problem | Likely cause | What to do |
| --- | --- | --- |
| Nothing happens when the pack is plugged in | Pack switch OFF; pack below the 6.36 V turn-on; or the pack's protection has switched it off after a deep discharge | Switch the pack ON. Plug in the USB-C adapter: it wakes the board and charges the pack. After a ship-mode shutdown, press SW1. |
| Board runs from the adapter but never from the battery | Pack switched off, a cell missing or reversed, pack over-discharged, or the pack's temperature cut-off is active | Unplug the adapter and the pack. Check the pack switch and each cell's orientation. Let a hot pack cool, then charge for at least 30 minutes. |
| 5V LED off on battery, but on with the adapter | Cells are flat, or the pack's over-discharge protection has switched it off | Charge with the adapter connected for at least 30 minutes. If it still will not run on battery, measure each cell; replace any cell below 2.0 V. |
| Battery will not charge at all | A cell is near 0 V, or a cell is above 4.23 V; the pack blocks charging in both cases | Measure each cell. Replace a dead cell with a new cell matching the other. |
| Pack switches off by itself and comes back later | Temperature cut-off (about 60 °C) | Improve ventilation round the pack, keep it out of the sun and away from the board's hot parts. |
| CHG LED blinking, battery not charging | Charge fault, such as the charge safety timer expiring or a cell over-voltage | Unplug and reconnect the adapter. If it continues, check each cell's voltage and replace mismatched cells. |
| i2cdetect -y 1 does not show 6b or 28 | I²C not enabled, or the board is not seated correctly | Install the ups-hat package (it enables I²C) and reboot. Check the header is not offset by a pin. |
| ups-hat log shows No such file or directory: /dev/i2c-1 | I²C is not enabled yet | Reboot after installing the package. If it continues, enable I²C with sudo raspi-config. |
| ups-hat log shows Remote I/O error | The board was off, or another device is holding the bus | Check the 5V LED is on. Remove other I²C HATs and try again. |
| Battery current reads 0 A, or no readings | The ups-hat service is not running | Start it with sudo systemctl enable --now ups-hat. |
| Charging at 8.4 V or 1 A after unplugging the pack | Disconnecting the pack resets the charger to its defaults | Normal. The service re-applies its settings within a few seconds. |
| Charge % wrong after fitting new cells | The estimate re-calibrates at the next full charge | Charge fully once with the adapter connected, and check ups-config --cells matches your pack. |
| Runtime much shorter than expected | Cells are mismatched or worn, so the weaker cell reaches its cut-off first | Replace all cells together with new matched cells. |
| Pi 5 shows a low-power or USB current warning | The Pi cannot detect a 5 A supply through the header | Add usb\_max\_current\_enable=1 and PSU\_MAX\_CURRENT=5000 (see [Raspberry Pi configuration](pi-configuration.md)). |
| Pi reboots or freezes under heavy load on battery | Cells nearly empty or not rated for the load current | Charge the cells. Use cells with a higher discharge rating, or move to the QUAD pack. |
| Charging is slow, or the battery drains while on mains | Adapter is 5 V only or under 27 W | Use a USB-C PD adapter of 27 W or more with 9 V or 15 V output. |
| Board stays on after sudo poweroff | The adapter is connected (by design), or the ups-hat package is not installed | On mains, unplug the adapter. Otherwise install the package. |
| Pi does not restart when mains returns | The Pi halted on mains and is waiting for its power button | Press the Pi's power button, or disconnect and reconnect the adapter. |

If the problem continues, note the board's revision and the output of `i2cdetect -y 1` and of journalctl -u ups-hat -n 50 before contacting support.
