# Power-off integration on linux boards (e.g. Raspberry Pi)

1. Install the library.
2. Copy `examples/` to `/usr/local/lib/ups-hat/examples/`.
3. Install the service and the shutdown hook, then start the service:

```sh
sudo cp examples/systemd/ups-hat.service /etc/systemd/system/
sudo cp examples/systemd/ups-hat-shutdown /usr/lib/systemd/system-shutdown/
sudo chmod +x /usr/lib/systemd/system-shutdown/ups-hat-shutdown
sudo systemctl enable --now ups-hat
```

Edit the `Environment=` lines in `ups-hat.service` to match your cells.

## The daemon

`examples/pi_daemon.py`:

- polls every 2 s and logs faults to the journal (`journalctl -u ups-hat`);
- writes `/run/ups-hat/status.json`;
- at low battery, creates `/run/ups-lowbatt` and runs `systemctl poweroff`.

## The shutdown hook

The hook runs as the very last step of a power-off or halt. It never acts on a reboot. It calls [`power_off()`][ups_hat.board.UPS.power_off], which does one of three things:

| Situation | Action |
|---|---|
| No adapter | Ship mode. The board goes dark. Press SW1 or plug in an adapter to start again. |
| Adapter connected, low-battery shutdown | System reset, so the Pi boots on mains instead of sitting halted. |
| Adapter connected, user shutdown | Nothing. The Pi halts and the board stays on. |
