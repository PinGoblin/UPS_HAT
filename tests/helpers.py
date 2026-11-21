"""Shared fixtures for the unittest suite (CPython only).

Every test that builds a [`UPS`][ups_hat.board.UPS] uses `BoardTestCase`, which swaps the
board module's clock for a simulated one so time-based fault rules can be driven quickly
and deterministically.
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from ups_hat import board as board_mod  # noqa: E402
from ups_hat import UPS  # noqa: E402
from sim import FakeI2C  # noqa: E402


class FakeClock:
    """Monotonic clock under test control."""

    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def set_adc(bus, **mv):
    """Set charger ADC channels in mV/mA; negative values are stored as two's complement."""
    for k, v in mv.items():
        bus.bq.adc[k] = int(v) & 0xFFFF


def mains(bus, **adc):
    """Adapter connected, charging (fast charge) at the given ADC values."""
    bus.bq.set_status(vbus=True, pg=True, chg=3)
    values = dict(vbus=9000, ibus=1200, vbat=7800, ibat=1000, vsys=7900)
    values.update(adc)
    set_adc(bus, **values)


def battery(bus, **adc):
    """No adapter: running from the pack."""
    bus.bq.set_status(vbus=False, pg=False, chg=0)
    values = dict(vbus=0, ibus=0, vbat=7600, ibat=-1500, vsys=7550)
    values.update(adc)
    set_adc(bus, **values)


class BoardTestCase(unittest.TestCase):
    """Base class: simulated clock, simulated chips, temporary directory."""

    def setUp(self):
        self.clock = FakeClock()
        self._real_now = board_mod.now_s
        board_mod.now_s = self.clock
        self.tmp = tempfile.mkdtemp(prefix="ups_hat_test_")

    def tearDown(self):
        board_mod.now_s = self._real_now
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.tmp, name)

    def make(self, bq=True, pd=True, attach=True, **kw):
        """Build a simulated bus and a UPS on it, adapter connected and charging."""
        bus = FakeI2C(bq=bq, pd=pd)
        if bus.bq:
            mains(bus)
        if bus.stusb and attach:
            bus.stusb.set_attached()
            bus.stusb.set_contract(2, 3.0)
        kw.setdefault("pi_monitor", False)
        return bus, UPS(bus, **kw)

    def run_for(self, ups, seconds, step=2.0):
        """Poll every `step` seconds of simulated time; return the last snapshot."""
        s = None
        end = self.clock.t + seconds
        while self.clock.t < end:
            self.clock.advance(step)
            s = ups.poll()
        return s

    def assertFault(self, snapshot, code, msg=None):
        self.assertIn(code, snapshot.fault_codes(), msg or snapshot.fault_codes())

    def assertNoFault(self, snapshot, code, msg=None):
        self.assertNotIn(code, snapshot.fault_codes(), msg or snapshot.fault_codes())


def bq_word(bus, reg):
    """Read a big-endian 16-bit value straight from the simulated charger registers."""
    r = bus.bq.r
    return (r[reg] << 8) | r[reg + 1]


try:  # optional: property-based tests
    import hypothesis  # noqa: F401
    HAVE_HYPOTHESIS = True
except ImportError:
    HAVE_HYPOTHESIS = False
