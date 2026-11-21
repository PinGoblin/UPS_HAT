"""Command line tool (Raspberry Pi / CPython).

    python3 -m ups_hat.cli status          one-off report
    python3 -m ups_hat.cli watch [secs]    live report
    python3 -m ups_hat.cli json            one snapshot as JSON
    python3 -m ups_hat.cli faults          list every fault code the library can report
    python3 -m ups_hat.cli registers       dump the charger registers
    python3 -m ups_hat.cli pd              USB-C PD configuration and contract
    python3 -m ups_hat.cli poweroff [low]  systemd-shutdown hook: ship mode / reset / nothing
"""

import sys
import json
import time

DEFAULT_STATE = "/var/lib/ups-hat/state.json"


def _ups(args):
    from . import UPS
    import os
    state = os.environ.get("UPS_HAT_STATE", DEFAULT_STATE)
    try:
        os.makedirs(os.path.dirname(state), exist_ok=True)
    except OSError:
        state = None
    return UPS(cells_parallel=int(os.environ.get("UPS_HAT_CELLS_PARALLEL", "1")),
                  cell_capacity_mah=float(os.environ.get("UPS_HAT_CELL_MAH", "3000")),
                  state_file=state)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    if cmd == "faults":
        from .faults import CATALOGUE, SEVERITY_NAMES
        for code in sorted(CATALOGUE):
            sev, src, msg, _ = CATALOGUE[code]
            print("{:28s} {:8s} {:9s} {}".format(code, SEVERITY_NAMES[sev], src, msg))
        return 0
    ups = _ups(argv)
    if cmd == "status":
        ups.poll()
        print(ups.report())
    elif cmd == "watch":
        period = float(argv[1]) if len(argv) > 1 else 2.0
        ups.poll()
        while True:
            print("\x1b[2J\x1b[H" + ups.report())
            time.sleep(period)
    elif cmd == "json":
        ups.poll()
        print(json.dumps(ups.poll().to_dict(), indent=2, default=str))
    elif cmd == "registers":
        for a, v in sorted(ups.charger.dump().items()):
            print("0x{:02X}: 0x{:02X}".format(a, v))
    elif cmd == "pd":
        print(json.dumps(ups.pd_config(), indent=2))
        print("contract:", ups.pd.contract)
    elif cmd == "poweroff":
        low = len(argv) > 1 and argv[1] == "low"
        print(ups.power_off(low_battery=low or None))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
