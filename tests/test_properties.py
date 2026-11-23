"""Property-based tests: invariants that must hold for any input, not just chosen examples.

Each property is a plain function. It is run by Hypothesis when it is installed (as in CI,
which then shrinks any failure to a minimal example) and otherwise by a seeded random
sampler, so the properties are always exercised.
"""

import json
import random
import unittest

import helpers
from helpers import BoardTestCase
from sim import FakeI2C
from ups_hat._compat import clamp, to_signed16
from ups_hat.battery import OCV_TABLE, BatteryMonitor, soc_from_ocv
from ups_hat.bq25798 import BQ25798
from ups_hat.bus import I2CDevice
from ups_hat.faults import CATALOGUE, Fault
from ups_hat.stusb4500 import PDO, STUSB4500, Contract
from test_bus import MemoryBus

SAMPLES = 300

# ---------------------------------------------------------------- the properties


def prop_signed16_round_trip(x):
    assert to_signed16(x & 0xFFFF) == x


def prop_clamp(x, lo, hi):
    lo, hi = min(lo, hi), max(lo, hi)
    c = clamp(x, lo, hi)
    assert lo <= c <= hi
    assert clamp(c, lo, hi) == c
    if lo <= x <= hi:
        assert c == x


def prop_set_field(initial, shift, width, value):
    width = min(width, 8 - shift)
    bus = MemoryBus()
    dev = I2CDevice(bus, 0x50)
    dev.set_u8(0x10, initial)
    dev.set_field(0x10, shift, width, value)
    mask = ((1 << width) - 1) << shift
    assert dev.field(0x10, shift, width) == value & ((1 << width) - 1)
    assert dev.u8(0x10) & ~mask & 0xFF == initial & ~mask & 0xFF, "other bits untouched"


CHARGER_SETTINGS = {  # property: (lowest, highest, resolution)
    "charge_voltage": (3.0, 18.8, 0.01),
    "charge_current": (0.05, 5.0, 0.01),
    "input_current_limit": (0.1, 3.3, 0.01),
    "input_voltage_limit": (3.6, 22.0, 0.1),
    "min_system_voltage": (2.5, 16.0, 0.25),
}


def prop_charger_setting(name, value):
    lo, hi, step = CHARGER_SETTINGS[name]
    c = BQ25798(FakeI2C(pd=False))
    setattr(c, name, value)
    got = getattr(c, name)
    assert lo - 1e-9 <= got <= hi + 1e-9, (name, value, got)
    assert abs(got - clamp(value, lo, hi)) <= step / 2 + 1e-9, (name, value, got)


def prop_nvm_pdos(v2, v3, a1, a2, a3, count):
    base = STUSB4500(FakeI2C(bq=False)).read_nvm()
    n, got = STUSB4500.decode_nvm_pdos(STUSB4500.encode_nvm_pdos(base, ((5.0, a1), (v2, a2), (v3, a3)), count))
    assert n == count
    assert got[0][0] == 5.0
    for want, have in ((v2, got[1][0]), (v3, got[2][0])):
        assert abs(have - clamp(want, 5.0, 20.0)) <= 0.025 + 1e-9
    for want, (_, have) in zip((a1, a2, a3), got):
        want = clamp(want, 0.0, 5.0)
        assert have <= want + 1e-9, "never more current than asked for"
        assert have == 0.0 if want < 0.5 else want - have < 0.5


def prop_pdo_and_contract_decode(raw):
    p = PDO(raw)
    assert 0 <= p.voltage <= 1023 * 0.05 + 1e-9 and 0 <= p.current <= 1023 * 0.01 + 1e-9
    k = Contract(raw)
    assert k.valid == (k.position != 0)
    repr(p), repr(k)


def prop_soc_monotonic(a, b):
    lo, hi = min(a, b), max(a, b)
    assert 0.0 <= soc_from_ocv(lo) <= soc_from_ocv(hi) <= 100.0


def prop_battery_monitor_bounds(steps):
    b = BatteryMonitor(parallel=1, cell_capacity_mah=3000, full_cell_voltage=4.1)
    t = 0.0
    for dt, vbat, ibat, done in steps:
        t += dt
        b.update(t, vbat, ibat, charge_done=done)
        assert 0.0 <= b.soc <= 100.0, b.soc
        assert 0.0 <= b.remaining_mah <= b.capacity_mah + 1e-6
        assert b.cycle_mah >= 0.0
    json.dumps(b.to_dict())


def prop_fault_formatting(code, data):
    f = Fault(code, data)
    assert str(f).startswith("[")
    json.dumps(f.to_dict(), default=str)


def prop_poll_never_raises(status, faults, flags, adc, pd_regs):
    """Whatever the chips report, poll() returns a snapshot and the report renders."""
    case = BoardTestCase("run")
    case.setUp()
    try:
        bus, ups = case.make()
        for i, v in enumerate(status):
            bus.bq.r[0x1B + i] = v
        bus.bq.r[0x20], bus.bq.r[0x21] = faults
        bus.bq.flags[:] = bytes(flags)
        for k, v in adc.items():
            bus.bq.adc[k] = v
        for reg, v in pd_regs:
            bus.stusb.r[reg] = v
        for _ in range(3):
            case.clock.advance(2)
            s = ups.poll()
            assert s.charger_ok and s.pd_ok
            json.dumps(s.to_dict(), default=str)
            assert isinstance(ups.report(s), str)
            assert s.worst_severity() in (-1, 0, 1, 2)
    finally:
        case.tearDown()


ADC_KEYS = ("ibus", "ibat", "vbus", "vac1", "vac2", "vbat", "vsys", "ts", "tdie", "dp", "dm")
PD_REGS = (0x0E, 0x10, 0x11, 0x13, 0x15, 0x29, 0x91, 0x92, 0x93, 0x94)

# ---------------------------------------------------------------- seeded random runner


class RandomSampleProperties(unittest.TestCase):
    """Always runs: SAMPLES seeded random examples per property."""

    def setUp(self):
        self.rng = random.Random(0x6B28)

    def repeat(self, prop, make_args, n=SAMPLES):
        for i in range(n):
            args = make_args(self.rng)
            try:
                prop(*args)
            except AssertionError as e:
                self.fail("%s failed for %r: %s" % (prop.__name__, args, e))

    def test_signed16(self):
        self.repeat(prop_signed16_round_trip, lambda r: (r.randint(-32768, 32767),))

    def test_clamp(self):
        self.repeat(prop_clamp, lambda r: (r.uniform(-100, 100), r.uniform(-50, 50), r.uniform(-50, 50)))

    def test_set_field(self):
        self.repeat(prop_set_field, lambda r: (r.randint(0, 255), r.randint(0, 7), r.randint(1, 8),
                                               r.randint(0, 511)))

    def test_charger_settings(self):
        names = sorted(CHARGER_SETTINGS)
        self.repeat(prop_charger_setting, lambda r: (r.choice(names), r.uniform(-1.0, 25.0)))

    def test_nvm_pdos(self):
        self.repeat(prop_nvm_pdos, lambda r: (r.uniform(0, 25), r.uniform(0, 25), r.uniform(-1, 6),
                                              r.uniform(-1, 6), r.uniform(-1, 6), r.randint(1, 3)), n=100)

    def test_pdo_contract(self):
        self.repeat(prop_pdo_and_contract_decode, lambda r: (r.getrandbits(32),))

    def test_soc(self):
        self.repeat(prop_soc_monotonic, lambda r: (r.uniform(2.5, 4.5), r.uniform(2.5, 4.5)))

    def test_battery_monitor(self):
        def steps(r):
            return ([(r.uniform(0.1, 900), r.uniform(5.0, 8.6), r.uniform(-6, 3), r.random() < 0.05)
                     for _ in range(r.randint(1, 60))],)
        self.repeat(prop_battery_monitor_bounds, steps, n=100)

    def test_fault_formatting(self):
        codes = sorted(CATALOGUE) + ["NOT_A_CODE"]
        values = [None, 0, -1, 3.14159, 1e9, "text", True]
        self.repeat(prop_fault_formatting, lambda r: (r.choice(codes), {
            "k%d" % i: r.choice(values) for i in range(r.randint(0, 4))}))

    def test_poll_fuzz(self):
        def args(r):
            return ([r.randint(0, 255) for _ in range(5)], (r.randint(0, 255), r.randint(0, 255)),
                    [r.randint(0, 255) for _ in range(6)], {k: r.randint(0, 0xFFFF) for k in ADC_KEYS},
                    [(reg, r.randint(0, 255)) for reg in PD_REGS])
        self.repeat(prop_poll_never_raises, args, n=60)


# ---------------------------------------------------------------- Hypothesis runner

if helpers.HAVE_HYPOTHESIS:
    from hypothesis import HealthCheck, given, settings, strategies as st

    FAST = settings(max_examples=200, deadline=None)
    SLOW = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    volts = st.floats(-1.0, 25.0, allow_nan=False)

    class HypothesisProperties(unittest.TestCase):
        @FAST
        @given(st.integers(-32768, 32767))
        def test_signed16(self, x):
            prop_signed16_round_trip(x)

        @FAST
        @given(st.floats(-100, 100), st.floats(-50, 50), st.floats(-50, 50))
        def test_clamp(self, x, lo, hi):
            prop_clamp(x, lo, hi)

        @FAST
        @given(st.integers(0, 255), st.integers(0, 7), st.integers(1, 8), st.integers(0, 511))
        def test_set_field(self, initial, shift, width, value):
            prop_set_field(initial, shift, width, value)

        @FAST
        @given(st.sampled_from(sorted(CHARGER_SETTINGS)), volts)
        def test_charger_settings(self, name, value):
            prop_charger_setting(name, value)

        @FAST
        @given(volts, volts, st.floats(-1, 6), st.floats(-1, 6), st.floats(-1, 6), st.integers(1, 3))
        def test_nvm_pdos(self, v2, v3, a1, a2, a3, count):
            prop_nvm_pdos(v2, v3, a1, a2, a3, count)

        @FAST
        @given(st.integers(0, 2 ** 32 - 1))
        def test_pdo_contract(self, raw):
            prop_pdo_and_contract_decode(raw)

        @FAST
        @given(st.floats(2.5, 4.5), st.floats(2.5, 4.5))
        def test_soc(self, a, b):
            prop_soc_monotonic(a, b)

        @SLOW
        @given(st.lists(st.tuples(st.floats(0.1, 900), st.floats(5.0, 8.6), st.floats(-6, 3), st.booleans()),
                        min_size=1, max_size=60))
        def test_battery_monitor(self, steps):
            prop_battery_monitor_bounds(steps)

        @FAST
        @given(st.sampled_from(sorted(CATALOGUE) + ["NOT_A_CODE"]),
               st.dictionaries(st.text(min_size=1, max_size=8),
                               st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
                               max_size=4))
        def test_fault_formatting(self, code, data):
            prop_fault_formatting(code, data)

        @SLOW
        @given(st.lists(st.integers(0, 255), min_size=5, max_size=5),
               st.tuples(st.integers(0, 255), st.integers(0, 255)),
               st.lists(st.integers(0, 255), min_size=6, max_size=6),
               st.fixed_dictionaries({k: st.integers(0, 0xFFFF) for k in ADC_KEYS}),
               st.tuples(*[st.tuples(st.just(reg), st.integers(0, 255)) for reg in PD_REGS]))
        def test_poll_fuzz(self, status, faults, flags, adc, pd_regs):
            prop_poll_never_raises(status, faults, flags, adc, list(pd_regs))
else:
    class HypothesisProperties(unittest.TestCase):
        @unittest.skip("hypothesis not installed: pip install -r requirements-test.txt")
        def test_hypothesis(self):
            pass


if __name__ == "__main__":
    unittest.main()
