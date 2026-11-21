# Software

The `ups_hat` library and its `ups-hat` service do everything the board needs from the Pi. They install from GitHub with pip (see [Raspberry Pi configuration](pi-configuration.md)). The [UPS HAT+ API](../api/index.md) section documents the library in full.

**What it does**

- Reads the charger every 2 seconds: battery voltage and current, input voltage and current, system voltage and charger status.
- Sets up the charger at start-up: watchdog off, charge voltage 8.2 V, charge current for your pack type, and an input current limit that matches the USB-C adapter.
- Tracks remaining charge by counting the current into and out of the battery, re-calibrated at every full charge.
- Reports faults, with advice, to the system journal (see [Fault codes](../api/faults.md)).
- Shuts the Pi down on battery power at 5 % remaining, or sooner if the battery voltage under load falls to 6.2 V.
- Switches the board fully off (ship mode) at the end of a power-off on battery.

**Commands**

| Command | What it does |
| --- | --- |
| `ups-hat status` | Prints a one-off report: readings, charge, adapter and faults. |
| `ups-hat watch` | Live report, refreshed every 2 seconds. |
| `ups-hat faults` | Lists every fault code and what to do about it. |
| `systemctl status ups-hat` | Shows whether the service is running. |
| `journalctl -u ups-hat -f` | Shows live readings and events. |
| `sudo systemctl restart ups-hat` | Applies changes to the pack type in `/etc/systemd/system/ups-hat.service` (run `sudo systemctl daemon-reload` first). |
| `cd UPS_HAT && git pull && sudo pip install --break-system-packages .` | Installs a software update, then `sudo systemctl restart ups-hat`. |
| `sudo systemctl disable --now ups-hat` then `sudo pip uninstall --break-system-packages ups-hat` | Removes the software. Also delete the service file and the shutdown hook. |

**Settings stay in the charger.** With the watchdog off, the charger keeps the software's settings even if the service stops. It returns to its hardware defaults (8.4 V, 1 A) only when the cells are disconnected, until the service runs again.
