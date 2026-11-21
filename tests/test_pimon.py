"""ups_hat.pimon: Raspberry Pi 5 supply monitoring, with vcgencmd mocked."""

import subprocess
import unittest
from unittest import mock

import helpers  # noqa: F401
from ups_hat.pimon import THROTTLE_BITS, PiPower


def vcgencmd(replies):
    """subprocess.run stand-in: replies maps the vcgencmd arguments to (returncode, stdout)."""
    def run(cmd, **kw):
        assert cmd[0] == "vcgencmd"
        assert kw.get("timeout"), "every call needs a timeout"
        reply = replies.get(tuple(cmd[1:]))
        if isinstance(reply, Exception):
            raise reply
        code, out = reply if reply is not None else (1, "")
        return subprocess.CompletedProcess(cmd, code, stdout=out, stderr="")
    return run


class PiPowerTests(unittest.TestCase):
    def pi(self, **replies):
        table = {("get_throttled",): (0, "throttled=0x0\n"), ("pmic_read_adc", "EXT5V_V"): (0, "EXT5V_V volt(24)=5.10840000V\n")}
        table.update({tuple(k.split()): v for k, v in replies.items()})
        self.table = table
        patcher = mock.patch("subprocess.run", side_effect=vcgencmd(table))
        patcher.start()
        self.addCleanup(patcher.stop)
        return PiPower()

    def test_available_on_a_pi(self):
        p = self.pi()
        self.assertTrue(p.available)
        self.assertEqual(p.throttled()["raw"], 0)
        self.assertAlmostEqual(p.ext5v(), 5.1084)

    def test_throttle_bits(self):
        p = self.pi()
        self.table[("get_throttled",)] = (0, "throttled=0x50005")
        th = p.throttled()
        self.assertTrue(th["under_voltage"] and th["throttled"] and th["under_voltage_occurred"]
                        and th["throttled_occurred"])
        self.assertFalse(th["arm_freq_capped"] or th["soft_temp_limit"])
        self.assertEqual(th["raw"], 0x50005)
        self.assertEqual(set(th) - {"raw"}, {name for _, name in THROTTLE_BITS})

    def test_not_a_pi(self):
        cases = [FileNotFoundError("vcgencmd"), (1, ""), (0, "error=1 error_msg=\"Command not registered\"")]
        for reply in cases:
            with self.subTest(reply=reply):
                p = self.pi(get_throttled=reply)
                self.assertFalse(p.available)
                self.assertIsNone(p.throttled())
                self.assertIsNone(p.ext5v())

    def test_pi4_has_no_pmic(self):
        p = self.pi(**{"pmic_read_adc EXT5V_V": (255, "")})
        self.assertTrue(p.available)
        self.assertIsNone(p.ext5v())

    def test_bad_outputs(self):
        p = self.pi()
        for out in ("", "garbage", "EXT5V_V volt(24)=notanumberV"):
            with self.subTest(out=out):
                self.table[("pmic_read_adc", "EXT5V_V")] = (0, out)
                self.assertIsNone(p.ext5v())
        self.table[("get_throttled",)] = (0, "")
        self.assertIsNone(p.throttled())

    def test_unexpected_error_during_detection(self):
        with mock.patch.object(PiPower, "_cmd", return_value=12345):   # not a string
            self.assertFalse(PiPower().available)

    def test_timeout_is_handled(self):
        p = self.pi()
        self.table[("get_throttled",)] = subprocess.TimeoutExpired("vcgencmd", 2)
        self.assertIsNone(p.throttled())


if __name__ == "__main__":
    unittest.main()
