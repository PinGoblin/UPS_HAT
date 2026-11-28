# Safety and limits

!!! danger "Calls that cut power to the Pi"
    **[`ship_mode()`][ups_hat.board.UPS.ship_mode], [`shutdown_mode()`][ups_hat.board.UPS.shutdown_mode] and [`system_reset()`][ups_hat.board.UPS.system_reset] cut power to the Pi immediately, or after 10 s with `delay=True`.** A Pi that is still running can corrupt its SD card or SSD. Call them only after the Pi has shut down, as the [shutdown hook](power-off.md) does.

!!! danger "USB-C controller NVM"
    **`restore_pd_defaults(write_nvm=True)` and `STUSB4500.write_nvm()` reprogram the USB-C controller's NVM, which has limited write endurance.** The PinGoblin UPS HAT+ leaves the factory programmed. Use `restore_pd_defaults()` without `write_nvm` to correct the settings until the next power cycle, and contact PinGoblin support if `PD_CONFIG_MISMATCH` returns after a restart.

!!! danger "Driver-level settings"
    **The `BQ25798` driver accepts values outside the PinGoblin UPS HAT+ limits, and can over-charge the cells.** Set the charge voltage and charge current through the `UPS` class, which keeps them within the limits below.

## Limits

| Setting | Limit |
|---|---|
| Charge voltage | 7.0–8.4 V (8.2 V by default) |
| Charge current | 0.1–3.0 A (1.5 A by default with `cells_parallel=1`, 2.0 A with `cells_parallel=2`) |
| Input current limit | 0.1–3.0 A |

The `UPS` class clamps a value outside these limits to the nearest limit.

## USB-C adapter

Use a USB PD adapter that offers 9 V or 15 V at 3 A. A 9 V adapter carries up to 22 W of Pi load; above that, and on any 5 V source, the UPS Pack makes up the difference.

## Boards without the ship FET

[`power_off()`][ups_hat.board.UPS.power_off], [`ship_mode()`][ups_hat.board.UPS.ship_mode], [`shutdown_mode()`][ups_hat.board.UPS.shutdown_mode] and [`system_reset()`][ups_hat.board.UPS.system_reset] need the ship FET. On a board built without it, pass `ship_fet=False`; these calls then raise [`NotSupported`][ups_hat.bus.NotSupported].

## Battery wiring protection

With `protect=True` (the default), `BAT_WIRING_FAULT` stops charging while the pack reads like a single or reversed cell (2.5–4.6 V). Charging starts again when the reading is normal.
