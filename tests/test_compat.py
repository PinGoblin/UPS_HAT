"""ups_hat._compat: the CPython/MicroPython portability layer."""

import time
import unittest
from unittest import mock

import helpers  # noqa: F401
from ups_hat import _compat


class SignedAndClampTests(unittest.TestCase):
    def test_to_signed16(self):
        cases = [(0, 0), (1, 1), (0x7FFF, 32767), (0x8000, -32768), (0xFFFF, -1), (0xFE0C, -500)]
        for raw, expected in cases:
            with self.subTest(raw=hex(raw)):
                self.assertEqual(_compat.to_signed16(raw), expected)

    def test_clamp(self):
        self.assertEqual(_compat.clamp(5, 0, 10), 5)
        self.assertEqual(_compat.clamp(-1, 0, 10), 0)
        self.assertEqual(_compat.clamp(11, 0, 10), 10)
        self.assertEqual(_compat.clamp(0, 0, 10), 0)
        self.assertEqual(_compat.clamp(10, 0, 10), 10)
        self.assertAlmostEqual(_compat.clamp(8.5, 7.0, 8.4), 8.4)

    def test_const_is_identity_on_cpython(self):
        self.assertFalse(_compat.MICROPYTHON)
        self.assertEqual(_compat.const(0x6B), 0x6B)


class ClockTests(unittest.TestCase):
    def test_ticks_use_monotonic_milliseconds(self):
        with mock.patch.object(time, "monotonic", return_value=12.3456):
            self.assertEqual(_compat.ticks_ms(), 12345)
            self.assertAlmostEqual(_compat.now_s(), 12.345)

    def test_ticks_diff(self):
        self.assertEqual(_compat.ticks_diff(1500, 1000), 500)

    def test_sleep_ms_converts_to_seconds(self):
        with mock.patch.object(time, "sleep") as sleep:
            _compat.sleep_ms(250)
        sleep.assert_called_once_with(0.25)

    def test_now_s_is_monotonic(self):
        a = _compat.now_s()
        b = _compat.now_s()
        self.assertGreaterEqual(b, a)


class WallTimeTests(unittest.TestCase):
    def test_set_clock(self):
        with mock.patch.object(time, "time", return_value=1763700000.0):
            self.assertEqual(_compat.wall_time(), 1763700000.0)

    def test_unset_board_clock_near_2000_is_unknown(self):
        with mock.patch.object(time, "time", return_value=946684800.0):
            self.assertIsNone(_compat.wall_time())

    def test_clock_error_is_unknown(self):
        with mock.patch.object(time, "time", side_effect=OSError):
            self.assertIsNone(_compat.wall_time())


class MicroPythonBranchTests(unittest.TestCase):
    """Load a second copy of _compat as MicroPython would see it: a `micropython` module
    with const(), and a `time` module with ticks_ms/ticks_diff/sleep_ms."""

    def load(self):
        import importlib.util
        import os
        import sys
        import types

        fake_time = types.SimpleNamespace(ticks_ms=mock.Mock(return_value=5000),
                                          ticks_diff=mock.Mock(side_effect=lambda a, b: (a - b) & 0x3FFFFFFF),
                                          sleep_ms=mock.Mock(), time=mock.Mock(return_value=1763700000))
        fake_mp = types.SimpleNamespace(const=lambda x: x)
        path = os.path.join(helpers.ROOT, "ups_hat", "_compat.py")
        spec = importlib.util.spec_from_file_location("_compat_as_micropython", path)
        mod = importlib.util.module_from_spec(spec)
        # (sys.implementation cannot be swapped: the import system itself reads it.)
        with mock.patch.dict(sys.modules, {"time": fake_time, "micropython": fake_mp}):
            spec.loader.exec_module(mod)
        return mod, fake_time

    def test_uses_micropython_ticks(self):
        mod, t = self.load()
        self.assertEqual(mod.ticks_ms(), 5000)
        self.assertEqual(mod.now_s(), 5.0)
        self.assertEqual(mod.ticks_diff(10, 20), (10 - 20) & 0x3FFFFFFF, "wraps like MicroPython")
        mod.sleep_ms(30)
        t.sleep_ms.assert_called_once_with(30)
        self.assertEqual(mod.const(7), 7)
        self.assertEqual(mod.wall_time(), 1763700000)


if __name__ == "__main__":
    unittest.main()
