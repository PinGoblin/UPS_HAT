"""Print the PinGoblin UPS HAT+ status once (Raspberry Pi).

    python3 pi_status.py           read the board
    python3 pi_status.py --mock    run without hardware (from a copy of the repository)
"""
import argparse
import sys

from ups_hat import UPS, UPSError


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mock", action="store_true", help="use a simulated board")
    args = ap.parse_args(argv)

    if args.mock:
        from mock_board import mock_i2c
        i2c = mock_i2c()
    else:
        i2c = None                    # /dev/i2c-1
    try:
        ups = UPS(i2c, cells_parallel=1, cell_capacity_mah=3000, pi_monitor=not args.mock)
        s = ups.poll()
    except OSError as e:
        print("I²C error: %s" % e, file=sys.stderr)
        return 1
    except UPSError as e:
        print("UPS HAT+ error: %s" % e, file=sys.stderr)
        return 1

    print(ups.report(s))
    print()
    print("On battery:", s.on_battery, " SoC:", s.soc, " Faults:", s.fault_codes())
    return 0 if s.charger_ok else 1


if __name__ == "__main__":
    sys.exit(main())
