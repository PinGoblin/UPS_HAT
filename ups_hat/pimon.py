"""Raspberry Pi 5 supply monitoring through ``vcgencmd`` (Linux only).

On MicroPython, or on a Pi without vcgencmd, :attr:`PiPower.available` is False
and every reading returns None.
"""

THROTTLE_BITS = (
    (0, "under_voltage"), (1, "arm_freq_capped"), (2, "throttled"), (3, "soft_temp_limit"),
    (16, "under_voltage_occurred"), (17, "arm_freq_capped_occurred"),
    (18, "throttled_occurred"), (19, "soft_temp_limit_occurred"),
)


class PiPower:
    def __init__(self):
        self.available = False
        self._run = None
        try:
            import subprocess
            self._sp = subprocess
            out = self._cmd("get_throttled")
            self.available = out is not None and out.startswith("throttled=")
        except Exception:
            self.available = False

    def _cmd(self, *args):
        try:
            p = self._sp.run(("vcgencmd",) + args, capture_output=True, text=True, timeout=2)
            if p.returncode != 0:
                return None
            return p.stdout.strip()
        except Exception:
            return None

    def throttled(self):
        """Dict of throttling flags, or None."""
        if not self.available:
            return None
        out = self._cmd("get_throttled")
        if not out or "=" not in out:
            return None
        v = int(out.split("=")[1], 16)
        d = {name: bool(v >> b & 1) for b, name in THROTTLE_BITS}
        d["raw"] = v
        return d

    def ext5v(self):
        """Pi 5 5 V input voltage (EXT5V_V) from the PMIC ADC, or None (Pi 4 and earlier)."""
        if not self.available:
            return None
        out = self._cmd("pmic_read_adc", "EXT5V_V")
        if not out or "=" not in out:
            return None
        try:
            return float(out.split("=")[1].rstrip("V"))
        except ValueError:
            return None
