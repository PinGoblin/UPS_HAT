"""Simulated PinGoblin UPS HAT+ for running the examples without hardware (--mock).

Uses the register-level simulator in tests/sim.py, so run the examples from a copy of
the repository. The simulated board is on mains power, charging a DUAL pack at 7.8 V
with a 15 V USB PD contract. Runs on CPython and MicroPython.
"""
import sys

try:
    _here = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
except NameError:                                   # frozen or pasted on a board
    _here = "."
sys.path.append(_here + "/../tests")

try:
    from sim import FakeI2C  # type: ignore
except ImportError:
    raise SystemExit("--mock needs tests/sim.py: run the example from a copy of the "
                     "UPS_HAT repository, for example python3 examples/pi_status.py --mock")


def mock_i2c():
    """Return a simulated I²C bus holding a working BQ25798 and STUSB4500."""
    bus = FakeI2C()
    bus.bq.set_status(vbus=True, pg=True, chg=3)
    for k, v in (("vbus", 15000), ("ibus", 900), ("vbat", 7800), ("ibat", 1000), ("vsys", 7900)):
        bus.bq.adc[k] = v & 0xFFFF
    bus.stusb.set_attached(True)
    bus.stusb.set_contract(3, 3.0)
    return bus
