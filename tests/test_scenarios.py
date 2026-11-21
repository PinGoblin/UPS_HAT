"""Runs every end-to-end scenario in tests/scenarios.py as its own unittest test.

scenarios.py stays framework-free so it also runs under MicroPython; this module gives
the same scenarios proper reporting under unittest and pytest.
"""

import os
import shutil
import tempfile
import unittest

import helpers  # noqa: F401  (sets up sys.path)
import scenarios
from ups_hat import board as board_mod


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self._real_now = board_mod.now_s
        board_mod.now_s = scenarios.CLOCK
        scenarios.CLOCK.t = 1000.0
        # Scenarios write state files in the working directory: use a temporary one.
        self._cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp(prefix="ups_hat_scn_")
        os.chdir(self._tmp)

    def tearDown(self):
        board_mod.now_s = self._real_now
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)


def _make(fn):
    def test(self):
        fn()
    test.__name__ = "test_" + fn.__name__
    test.__doc__ = fn.__name__.replace("_", " ")
    return test


for _fn in scenarios.TESTS:
    setattr(ScenarioTests, "test_" + _fn.__name__, _make(_fn))


class ScenarioScriptTests(unittest.TestCase):
    def test_every_scenario_is_registered(self):
        self.assertGreaterEqual(len(scenarios.TESTS), 24)
        names = [f.__name__ for f in scenarios.TESTS]
        self.assertEqual(len(names), len(set(names)), "duplicate scenario names")


if __name__ == "__main__":
    unittest.main()
