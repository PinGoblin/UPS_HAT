"""Raspberry Pi 5 supply monitoring through `vcgencmd` (Linux only).

Utilises the `vcgencmd` linux command on a Raspberry Pi to enable Pi specific
monitoring. This includes Pi-specific faults (PI_UNDERVOLTAGE, 
PI_UNDERVOLTAGE_OCCURRED, OUTPUT_5V_FAULT, PI_EXTERNAL_SUPPLY) and the Pi's 
5 V reading in snapshots. If utilised on a non-Raspberry Pi board 
[`PiPower.available`][ups_hat.pimon.PiPower] will be `False` and every PiPower 
attribute will return `None`. In this case, utilise the on-board monitoring 
provided by the PinGoblin UPS HAT+ itself.
"""

THROTTLE_BITS = (
    (0, "under_voltage"), (1, "arm_freq_capped"), (2, "throttled"), (3, "soft_temp_limit"),
    (16, "under_voltage_occurred"), (17, "arm_freq_capped_occurred"),
    (18, "throttled_occurred"), (19, "soft_temp_limit_occurred"),
)


class PiPower:
    """Reads the Pi's own supply state through `vcgencmd`.

    Attributes:
        available (bool): `vcgencmd get_throttled` worked when the object was created.
    """

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
        """Read the firmware's throttling flags.

        Returns:
            A dict of booleans (`under_voltage`, `arm_freq_capped`, `throttled`,
            `soft_temp_limit` and the matching `*_occurred` flags since boot) plus `raw`, the
            integer value. `None` if unavailable.
        """
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
        """Read the Pi 5's 5 V input voltage from its PMIC ADC (`EXT5V_V`).

        Returns:
            Volts, or `None` on a Pi 4 or earlier, or if unavailable.
        """
        if not self.available:
            return None
        out = self._cmd("pmic_read_adc", "EXT5V_V")
        if not out or "=" not in out:
            return None
        try:
            return float(out.split("=")[1].rstrip("V"))
        except ValueError:
            return None
