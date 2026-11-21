"""UPS HAT+ monitoring daemon for Raspberry Pi OS.

- Polls the board every 2 s.
- Logs every new and cleared fault (to the journal when run under systemd).
- Writes the latest snapshot to /run/ups-hat/status.json for other programs.
- Shuts the Pi down cleanly when the battery is low. The shutdown hook
  (ups-hat-shutdown) then puts the board in ship mode, or power-cycles the
  Pi if mains returned during the shutdown.

Settings come from environment variables (see ups-hat.service).
"""
import json
import os
import signal
import subprocess
import sys
import time

from ups_hat import UPS

RUN_DIR = "/run/ups-hat"
LOWBATT_FLAG = "/run/ups-lowbatt"


def log(msg):
    print(msg, flush=True)


def main():
    os.makedirs(RUN_DIR, exist_ok=True)
    os.makedirs("/var/lib/ups-hat", exist_ok=True)
    ups = UPS(
        cells_parallel=int(os.environ.get("UPS_HAT_CELLS_PARALLEL", "1")),
        cell_capacity_mah=float(os.environ.get("UPS_HAT_CELL_MAH", "3000")),
        charge_voltage=float(os.environ.get("UPS_HAT_CHARGE_VOLTAGE", "8.2")),
        low_battery_soc=float(os.environ.get("UPS_HAT_LOW_SOC", "5")),
        state_file="/var/lib/ups-hat/state.json",
    )
    ups.on_fault(lambda f: log("FAULT %s" % f))
    ups.on_clear(lambda f: log("CLEARED %s" % f.code))
    def stop(signum, frame):
        # systemd stops the service during every shutdown: record a clean stop.
        ups.save_state(clean=True)
        log("ups_hat daemon stopped")
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    log("ups_hat daemon started")
    shutting_down = False
    while True:
        s = ups.poll()
        tmp = os.path.join(RUN_DIR, "status.json.tmp")
        with open(tmp, "w") as f:
            json.dump(s.to_dict(), f, default=str)
        os.replace(tmp, os.path.join(RUN_DIR, "status.json"))
        if s.should_shutdown and not shutting_down:
            shutting_down = True
            log("Battery low (%.2f V, %s %%): shutting down" % (s.vbat, s.soc))
            ups.save_state()
            open(LOWBATT_FLAG, "w").close()
            subprocess.call(["systemctl", "poweroff"])
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
