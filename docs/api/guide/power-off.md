# Power-off integration (Raspberry Pi OS)

The service shuts the Pi down cleanly at low battery. The shutdown hook then turns the PinGoblin UPS HAT+ off, so the UPS Pack is not drained while the Pi is halted.

## Install

1. [Install the library](install.md).
2. Copy the examples and install the service and the shutdown hook:

    ```sh
    sudo mkdir -p /usr/local/lib/ups-hat
    sudo cp -r examples /usr/local/lib/ups-hat/
    sudo cp examples/systemd/ups-hat.service /etc/systemd/system/
    sudo cp examples/systemd/ups-hat-shutdown /usr/lib/systemd/system-shutdown/
    sudo chmod +x /usr/lib/systemd/system-shutdown/ups-hat-shutdown
    ```

3. Edit the `Environment=` lines in `/etc/systemd/system/ups-hat.service` to match your pack: `UPS_HAT_CELLS_PARALLEL=1` for a DUAL pack, `2` for a QUAD pack.
4. Start the service:

    ```sh
    sudo systemctl enable --now ups-hat
    ```

## The service

`examples/pi_daemon.py`:

- Polls every 2 s and logs every fault to the journal (`journalctl -u ups-hat`).
- Writes the latest status to `/run/ups-hat/status.json` for other programs.
- At low battery, creates `/run/ups-lowbatt` and runs `systemctl poweroff`.

## The shutdown hook

The hook runs as the last step of a power-off or halt. It never acts on a reboot. It calls [`power_off()`][ups_hat.board.UPS.power_off], which does one of three things:

| Situation | Action |
|---|---|
| No adapter | Ship mode. The board turns off. Press SW1 or plug in an adapter to start again. |
| Adapter connected, low-battery shutdown | System reset, so the Pi starts again on mains power instead of staying halted. |
| Adapter connected, shutdown by the user | Nothing. The Pi halts and the board stays on. |
