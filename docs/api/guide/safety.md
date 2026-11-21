# Safety and limits

- The charge voltage is clamped to 7.0–8.4 V, the charge current to 3.0 A and the input current limit to 3.0 A.
- The USB-C adapter must offer USB PD at 9 V or 15 V, 3 A. With 9 V the adapter covers about 22 W of Pi load; above that, and with any 5 V source, the pack makes up the difference.
- [`power_off()`][ups_hat.board.UPS.power_off], [`ship_mode()`][ups_hat.board.UPS.ship_mode], [`shutdown_mode()`][ups_hat.board.UPS.shutdown_mode] and [`system_reset()`][ups_hat.board.UPS.system_reset] need the SDRV ship FET. On a board built without it, pass `ship_fet=False`; these calls then raise [`NotSupported`][ups_hat.bus.NotSupported].
- `BAT_WIRING_FAULT` stops charging while the pack reads like a single or reversed cell (2.5–4.6 V). Charging resumes when the reading is normal again.
- Inferred battery faults are estimates. Confirm them by measuring the cells before replacing anything.

## Testing without hardware

`tests/sim.py` simulates both chips at register level. Run the tests with either interpreter:

```sh
python3 tests/test_ups_hat.py
micropython tests/test_ups_hat.py
```
