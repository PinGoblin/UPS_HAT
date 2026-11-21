# Operation

The board has no on-board processor. The Raspberry Pi reads the board over I²C and decides when to shut down, so the `ups-hat` service must be installed for safe shutdowns (see [Raspberry Pi configuration](pi-configuration.md)).

| State | What happens | LEDs |
| --- | --- | --- |
| Mains power | Adapter powers the Pi and charges the battery. | 5V on; CHG on while charging |
| Battery power | Battery powers the Pi with no interruption. | 5V on; CHG off |
| Low battery | The ups-hat service shuts the Pi down at 5 % remaining. | 5V on until shutdown completes |
| Off (ship mode) | After a shutdown on battery, the board disconnects the battery. Standby drain is a few microamps. | All off |
| Hardware cut-off | If no software acts, the output switches off at about 5.6 V pack voltage. | 5V off |

**Turning on:** plug in the USB-C adapter, or press SW1 briefly to start from battery.

**Turning off:** shut down the Pi normally (`sudo poweroff`). On battery, the shutdown hook then switches the board off. On mains, the board stays powered and the Pi halts; unplug the adapter or restart the Pi with its power button.

**After a power cut:** when the adapter is reconnected, the board wakes and the Pi starts automatically, even if the battery was flat.

**Pack switch and temperature cut-off.** The pack's own switch turns its output off completely; use it for storage and transport. If the cells reach about 60 °C, the pack switches itself off. On the HAT, after the switch is turned back ON or the cells have cooled below about 56 °C, the pack stays off until the HAT next has USB-C power: connect the adapter to bring it back. Without an adapter connected, the Pi then loses power without a clean shutdown, so give the pack ventilation and keep it out of the sun.

**Temperature limits.** Keep the board, the pack and the Pi within these limits:

| Condition | Min | Max | Notes |
| --- | --- | --- | --- |
| Running, on the adapter or on battery | 0 °C | 45 °C | Air around the board and the pack. The Raspberry Pi 5 itself is rated to 50 °C |
| Charging the cells | 0 °C | 45 °C | Nothing on the board or the pack stops charging outside this range |
| Cells, at any time | — | 60 °C | The pack switches itself off at about 60 °C and back on below about 56 °C |
| Storage, board only | −20 °C | 60 °C | In its anti-static bag |
| Storage, cells, under a month | −20 °C | 45 °C | For long-term storage keep them at 10–25 °C |

**Hot cars.** On a hot day the cabin of a parked car can reach 60–75 °C, beyond every limit above. Do not leave the pack in a parked car in summer. If it gets that hot, the pack switches itself off. A Pi powered from the car keeps running from the adapter, but it has no battery backup until the pack cools.

**Cold.** Frosts below 0 °C occur in inland and alpine Australia. Do not charge the pack below 0 °C: charging a cold lithium cell plates lithium inside it, which permanently reduces its capacity and can cause an internal short. Let a cold pack warm to room temperature before connecting the adapter.

**Shutdown hook.** The shutdown hook (installed in [Raspberry Pi configuration](pi-configuration.md)) runs at the very end of every power-off. If no adapter is connected, it puts the charger into ship mode, which switches the board off immediately. If the adapter is connected and the shutdown was for low battery, it power-cycles the Pi so that it boots on mains. It does nothing on a reboot, or after a normal shutdown on mains.
