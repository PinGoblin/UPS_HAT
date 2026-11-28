"""Every documented example runs: the docstring Examples and the scripts in examples/ (--mock)."""

import ast
import contextlib
import io
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

import helpers
from helpers import BoardTestCase
from sim import FakeI2C
import ups_hat
from ups_hat import bus as bus_mod

MODULES = ("board", "bq25798", "stusb4500", "battery", "bus", "faults", "pimon")
BLOCK = re.compile(r"```python\n(.*?)```", re.S)


def docstring_examples():
    """Yield (qualified name, code) for every ```python block in an Example section."""
    for mod in MODULES:
        path = os.path.join(helpers.ROOT, "ups_hat", mod + ".py")
        tree = ast.parse(open(path).read())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                continue
            doc = ast.get_docstring(node) or ""
            if "Example:" not in doc:
                continue
            section = doc.split("Example:", 1)[1]
            for i, code in enumerate(BLOCK.findall(section)):
                yield "%s.%s[%d]" % (mod, node.name, i), _dedent(code)


def _dedent(code):
    lines = [ln for ln in code.split("\n")]
    pad = min((len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()), default=0)
    return "\n".join(ln[pad:] for ln in lines)


class FakeLinuxI2C(FakeI2C):
    """Stands in for LinuxI2C(1) in the examples: a simulated bus that is a context manager."""

    def __init__(self, bus=1):
        super().__init__()
        helpers.mains(self)
        self.stusb.set_attached()
        self.stusb.set_contract(3, 3.0)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def scan(self):
        return sorted(self.devices)

    def close(self):
        pass


class DocstringExamples(BoardTestCase):
    def namespace(self):
        from ups_hat import UPS, BatteryMonitor, I2CDevice
        from ups_hat.pimon import PiPower
        import time
        bus = FakeLinuxI2C()
        ups = UPS(bus, pi_monitor=False)
        bm = BatteryMonitor(parallel=1, cell_capacity_mah=3000)
        bm.update(time.monotonic(), vbat=7.6, ibat=-1.2)
        ns = {"ups": ups, "chg": ups.charger, "pd": ups.pd, "bm": bm, "i2c": bus, "time": time,
              "dev": I2CDevice(bus, 0x6B, "BQ25798"), "I2CDevice": I2CDevice, "saved": bm.to_dict(),
              "fault": ups_hat.Fault("BAT_LOW"), "pi": PiPower(), "STUSB4500": ups_hat.STUSB4500}
        return ns

    def test_every_docstring_example_runs(self):
        examples = list(docstring_examples())
        self.assertGreater(len(examples), 150)
        patches = [mock.patch.object(ups_hat, "LinuxI2C", FakeLinuxI2C),
                   mock.patch.object(bus_mod, "LinuxI2C", FakeLinuxI2C),
                   mock.patch.object(ups_hat, "open_bus", lambda bus=1: FakeLinuxI2C()),
                   mock.patch("ups_hat.board.UPS.run", lambda self, *a, **k: None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        for name, code in examples:
            with self.subTest(example=name):
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(code, name, "exec"), self.namespace())


class ExampleScripts(unittest.TestCase):
    def run_example(self, *argv):
        env = dict(os.environ, PYTHONPATH=helpers.ROOT)
        return subprocess.run([sys.executable] + list(argv), cwd=helpers.ROOT, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_pi_status_mock(self):
        p = self.run_example("examples/pi_status.py", "--mock")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("SoC", p.stdout)

    def test_pi_daemon_mock(self):
        p = self.run_example("examples/pi_daemon.py", "--mock", "--polls", "2")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("status written to", p.stdout)

    def test_micropython_example_mock_on_cpython(self):
        # Runs the MicroPython example's --mock path; machine is never imported.
        p = self.run_example("examples/micropython_main.py", "--mock")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("mains", p.stdout)


if __name__ == "__main__":
    unittest.main()
