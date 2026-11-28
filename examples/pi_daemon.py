"""PinGoblin UPS HAT+ monitoring service for Raspberry Pi OS.

- Polls the board every 2 s.
- Logs every new and cleared fault (to the journal when run under systemd).
- Writes the latest snapshot to /run/ups-hat/status.json for other programs.
- Shuts the Pi down cleanly when the battery is low. The shutdown hook
  (ups-hat-shutdown) then puts the board in ship mode, or power-cycles the
  Pi if mains power returned during the shutdown.

Settings come from environment variables (see ups-hat.service).

    python3 pi_daemon.py                    run as the service does
    python3 pi_daemon.py --mock --polls 3   run without hardware (from a copy of the
                                            repository); writes to a temporary folder
                                            and never shuts the Pi down
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

from ups_hat import UPS, UPSError

LOWBATT_FLAG = "/run/ups-lowbatt"


def log(msg):
    print(msg, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="PinGoblin UPS HAT+ monitoring service")
    ap.add_argument("--mock", action="store_true", help="use a simulated board")
    ap.add_argument("--polls", type=int, default=None, help="stop after this many polls")
    args = ap.parse_args(argv)

    if args.mock:
        from mock_board import mock_i2c
        i2c = mock_i2c()
        run_dir = tempfile.mkdtemp(prefix="ups-hat-")
        state_file = None
    else:
        i2c = None                    # /dev/i2c-1
        run_dir = "/run/ups-hat"
        state_file = "/var/lib/ups-hat/state.json"
        os.makedirs("/var/lib/ups-hat", exist_ok=True)
    os.makedirs(run_dir, exist_ok=True)

    try:
        ups = UPS(
            i2c,
            cells_parallel=int(os.environ.get("UPS_HAT_CELLS_PARALLEL", "1")),
            cell_capacity_mah=float(os.environ.get("UPS_HAT_CELL_MAH", "3000")),
            charge_voltage=float(os.environ.get("UPS_HAT_CHARGE_VOLTAGE", "8.2")),
            low_battery_soc=float(os.environ.get("UPS_HAT_LOW_SOC", "5")),
            state_file=state_file,
            pi_monitor=not args.mock,
        )
    except ValueError as e:
        log("Configuration error: %s. Check the Environment= lines in ups-hat.service." % e)
        return 2
    except OSError as e:
        log("I²C error: %s" % e)
        return 1
    except UPSError as e:
        log("UPS HAT+ error: %s" % e)
        return 1

    ups.on_fault(lambda f: log("FAULT %s" % f))
    ups.on_clear(lambda f: log("CLEARED %s" % f.code))

    def stop(signum, frame):
        # systemd stops the service during every shutdown: record a clean stop.
        ups.save_state(clean=True)
        log("ups_hat service stopped")
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    log("ups_hat service started")
    shutting_down = False
    n = 0
    while args.polls is None or n < args.polls:
        s = ups.poll()
        tmp = os.path.join(run_dir, "status.json.tmp")
        with open(tmp, "w") as f:
            json.dump(s.to_dict(), f, default=str)
        os.replace(tmp, os.path.join(run_dir, "status.json"))
        if s.should_shutdown and not shutting_down:
            shutting_down = True
            log("Battery low (%.2f V, %s %%): shutting down" % (s.vbat, s.soc))
            ups.save_state()
            if args.mock:
                log("--mock: not shutting down")
            else:
                open(LOWBATT_FLAG, "w").close()
                subprocess.call(["systemctl", "poweroff"])
        n += 1
        if args.polls is None or n < args.polls:
            time.sleep(0 if args.mock else 2)
    if args.mock:
        log("status written to %s" % os.path.join(run_dir, "status.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
