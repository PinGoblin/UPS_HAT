"""ups_hat.cli: the ups-hat command, run against the simulators."""

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

import helpers
from helpers import BoardTestCase, battery
from ups_hat import cli
from ups_hat.faults import CATALOGUE


class CliTests(BoardTestCase):
    def setUp(self):
        super().setUp()
        self.bus, self.ups = self.make()
        patcher = mock.patch.object(cli, "_ups", return_value=self.ups)
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_faults_lists_every_code_without_hardware(self):
        code, out = self.run_cli("faults")
        self.assertEqual(code, 0)
        self.factory.assert_not_called()
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), len(CATALOGUE))
        self.assertEqual([ln.split()[0] for ln in lines], sorted(CATALOGUE))

    def test_status_is_default(self):
        for argv in ((), ("status",)):
            with self.subTest(argv=argv):
                code, out = self.run_cli(*argv)
                self.assertEqual(code, 0)
                self.assertIn("Power source : adapter", out)

    def test_json(self):
        code, out = self.run_cli("json")
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertAlmostEqual(d["vbat"], 7.8)
        self.assertTrue(d["charger_ok"])

    def test_registers(self):
        code, out = self.run_cli("registers")
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 0x49)
        self.assertEqual(lines[0x48], "0x48: 0x19")

    def test_pd(self):
        code, out = self.run_cli("pd")
        self.assertEqual(code, 0)
        self.assertIn('"ram_count": 3', out)
        self.assertIn("contract: Contract(source PDO 2, 3.00 A)", out)

    def test_poweroff(self):
        battery(self.bus)
        self.assertEqual(self.run_cli("poweroff"), (0, "ship\n"))
        helpers.mains(self.bus)
        self.assertEqual(self.run_cli("poweroff"), (0, "none\n"))
        self.assertEqual(self.run_cli("poweroff", "low"), (0, "reset\n"))

    def test_watch_until_interrupted(self):
        with mock.patch.object(cli.time, "sleep", side_effect=[None, KeyboardInterrupt]) as sleep:
            with self.assertRaises(KeyboardInterrupt):
                self.run_cli("watch", "0.5")
        sleep.assert_called_with(0.5)

    def test_unknown_command(self):
        code, out = self.run_cli("frobnicate")
        self.assertEqual(code, 2)
        self.assertIn("Command-line tool", out)


class FactoryTests(unittest.TestCase):
    """cli._ups reads its settings from the environment."""

    def test_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch("os.makedirs") as mk, mock.patch("ups_hat.UPS") as UPS:
            cli._ups([])
        mk.assert_called_once_with("/var/lib/ups-hat", exist_ok=True)
        UPS.assert_called_once_with(cells_parallel=1, cell_capacity_mah=3000.0, state_file=cli.DEFAULT_STATE)

    def test_environment(self):
        env = {"UPS_HAT_CELLS_PARALLEL": "2", "UPS_HAT_CELL_MAH": "3500", "UPS_HAT_STATE": "/tmp/x/s.json"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("os.makedirs"), mock.patch("ups_hat.UPS") as UPS:
            cli._ups([])
        UPS.assert_called_once_with(cells_parallel=2, cell_capacity_mah=3500.0, state_file="/tmp/x/s.json")

    def test_unwritable_state_dir_disables_state(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch("os.makedirs", side_effect=PermissionError), mock.patch("ups_hat.UPS") as UPS:
            cli._ups([])
        self.assertIsNone(UPS.call_args.kwargs["state_file"])

    def test_module_entry_point(self):
        import runpy
        import sys
        with mock.patch("sys.argv", ["ups-hat", "faults"]), redirect_stdout(io.StringIO()), \
                mock.patch.dict(sys.modules):
            sys.modules.pop("ups_hat.cli", None)     # run it fresh, as `python -m ups_hat.cli` would
            with self.assertRaises(SystemExit) as cm:
                runpy.run_module("ups_hat.cli", run_name="__main__")
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
