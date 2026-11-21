# Software

The `ups-hat` package does everything the board needs from the Pi. It installs from the UPS HAT+ APT repository (see [Raspberry Pi configuration](pi-configuration.md)) and updates with `sudo apt upgrade`.

**What it does**

- Reads the charger every second: battery voltage and current, input voltage and current, system voltage and charger status.
- Sets up the charger at start-up: watchdog off, charge voltage 8.2 V, charge current for your pack type, and an input current limit that matches the USB-C adapter.
- Tracks remaining charge by counting the current into and out of the battery, re-calibrated at every full charge.
- Shuts the Pi down on battery power at 5 % remaining, or sooner if the battery voltage under load falls to 6.2 V.
- Switches the board fully off (ship mode) at the end of a power-off on battery.

**Commands**

| Command | What it does |
| --- | --- |
| `sudo ups-config --cells 2S1P` or `--cells 2S2P` | Sets the pack type and so the charge current. Use 2S1P for the DUAL pack, and 2S2P for the QUAD or a larger third-party pack. Saved in `/etc/ups-hat.conf`. |
| `systemctl status ups-hat` | Shows whether the service is running. |
| `journalctl -u ups-hat -f` | Shows live readings and events. |
| `sudo apt upgrade` | Installs software updates with the rest of the system. |
| `sudo apt remove ups-hat` | Removes the software. |

**Settings stay in the charger.** With the watchdog off, the charger keeps the software's settings even if the service stops. It returns to its hardware defaults (8.4 V, 1 A) only when the cells are disconnected, until the service runs again.
