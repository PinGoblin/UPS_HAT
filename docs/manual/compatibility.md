# Compatibility

The board is designed for the Raspberry Pi 5 and works with any Raspberry Pi that has the standard 40-pin header.

| Raspberry Pi model | Supported | Notes |
| --- | --- | --- |
| Raspberry Pi 5 (all memory sizes) | Yes, fully | Full 5 A output. HAT+ ID read automatically. |
| Raspberry Pi 4 Model B | Yes | Power and battery monitoring work. The HAT+ ID may not be read by older firmware; this does not affect operation. |
| Raspberry Pi 3 Model B / B+ | Yes | As for Pi 4. |
| Raspberry Pi Zero 2 W / Zero W | Electrically yes | The board is larger than a Zero and overhangs it. |
| Raspberry Pi 400 / 500, Compute Modules | No | No standard 40-pin HAT header. |

**Operating system:** Raspberry Pi OS (Bookworm or later) is recommended. Any Linux with I²C support and Python 3 can run the monitoring software.

**Other HATs:** the board uses only header pins 3 and 5 (I²C1) and GPIO24 (EEPROM write-protect). Other HATs that use I²C1 can share the bus, as long as they do not use addresses 0x28 or 0x6B.

**Cases and coolers:** the Raspberry Pi Active Cooler and most low-profile heatsinks fit underneath when the board is mounted on standoffs tall enough to clear them. Check the clearance before tightening the screws.
