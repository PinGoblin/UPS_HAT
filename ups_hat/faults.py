"""Fault codes reported by [`UPS`][ups_hat.board.UPS].

Each fault has a stable string code (safe to log or match on), a severity, the source it
came from, a one-line message and advice for the user. The full list is
[`CATALOGUE`][ups_hat.faults.CATALOGUE]; the [Fault codes](../faults.md) page shows it
as a table.

| Source | Meaning |
|---|---|
| `charger` | Read from BQ25798 registers. |
| `pd` | Read from STUSB4500 registers. |
| `bus` | An I²C device did not answer. |
| `inferred` | Worked out from measurements over time: a strong hint, not proof. |
| `pi` | Read from the Raspberry Pi 5 firmware (`vcgencmd`). |
"""

INFO = 0
"""Severity 0: information, no action needed."""
WARNING = 1
"""Severity 1: needs attention."""
CRITICAL = 2
"""Severity 2: needs action now."""
SEVERITY_NAMES = ("info", "warning", "critical")

# code: (severity, source, message, advice)
CATALOGUE = {
    # ---- bus --------------------------------------------------------------------------
    "BUS_CHARGER_MISSING": (CRITICAL, "bus", "Charger (BQ25798, 0x6B) is not answering on I²C.",
                            "Check that I²C is enabled and the HAT is fully seated on the header. If the fault returns, contact PinGoblin support."),
    "BUS_PD_MISSING": (WARNING, "bus", "USB-C controller (STUSB4500, 0x28) is not answering on I²C.",
                       "Power is unaffected, but USB PD information is unavailable. Re-seat the HAT on the header."),
    # ---- charger, measured -----------------------------------------------------------
    "CHG_VBUS_OVP": (CRITICAL, "charger", "USB-C input over-voltage.", "Unplug the adapter: It is faulty or not USB-C PD compliant."),
    "CHG_VAC_OVP": (CRITICAL, "charger", "Input (VAC) over-voltage.", "Unplug the adapter: It is faulty or not USB-C PD compliant."),
    "CHG_VBAT_OVP": (CRITICAL, "charger", "Battery over-voltage.",
                     "Check that the cells are 3.6–3.7 V lithium-ion cells. Charging is stopped."),
    "CHG_IBUS_OCP": (WARNING, "charger", "Input over-current.", "The load is above what the adapter can supply. Use a USB-C PD adapter that offers 15 V at 3 A, or reduce the load on the Pi."),
    "CHG_IBAT_OCP": (CRITICAL, "charger", "Battery over-current.", "Unplug the pack and check its lead and cells for damage. If the fault returns, contact PinGoblin support."),
    "CHG_CONVERTER_OCP": (CRITICAL, "charger", "Charger converter over-current.", "Remove the Pi and accessories and restart. If the fault returns, contact PinGoblin support."),
    "CHG_VSYS_SHORT": (CRITICAL, "charger", "System rail (SYS) short circuit.", "Remove the Pi and accessories and restart. If the fault returns, contact PinGoblin support."),
    "CHG_VSYS_OVP": (CRITICAL, "charger", "System rail (SYS) over-voltage.", "Unplug the adapter and the pack, and contact PinGoblin support."),
    "CHG_THERMAL_SHUTDOWN": (CRITICAL, "charger", "Charger thermal shutdown.", "Improve airflow, and reduce the load or the charge current."),
    "CHG_IBAT_REGULATION": (INFO, "charger", "Battery discharge current is being limited.", ""),
    "CHG_TIMER_EXPIRED": (WARNING, "charger", "Fast-charge safety timer expired before the battery was full.",
                          "The cells may be worn, or the charge current is too low for their capacity (check cells_parallel)."),
    "CHG_PRECHARGE_TIMER_EXPIRED": (WARNING, "charger", "Pre-charge timer expired: The battery did not recover from deep discharge.",
                                    "A cell is probably damaged. Replace both cells."),
    "CHG_TRICKLE_TIMER_EXPIRED": (WARNING, "charger", "Trickle-charge timer expired: The battery voltage stayed very low.",
                                  "Check the pack lead. A cell may be dead or the pack fuse blown."),
    "CHG_WATCHDOG_EXPIRED": (WARNING, "charger", "Charger I²C watchdog expired: Charger settings returned to defaults.",
                             "No action needed: The library re-applies its settings."),
    "CHG_THERMAL_REGULATION": (INFO, "charger", "Charger is reducing current to limit its temperature.", "Improve airflow."),
    "CHG_INPUT_LIMITED": (INFO, "charger", "Adapter is at its current or voltage limit.",
                          "Use a USB-C PD adapter that offers 9 V or 15 V at 3 A (15 V for full load while charging)."),
    "CHG_POOR_SOURCE": (WARNING, "charger", "Weak adapter detected.", "Use a USB-C PD adapter that offers 9 V or 15 V at 3 A, and a good cable."),
    "CHG_RESET_DETECTED": (WARNING, "charger", "Charger settings had returned to defaults (power-on reset).",
                           "No action needed if it happens once: The library has re-applied its settings. If it repeats, check the pack lead, its XT30 plug and the cells."),
    # ---- PD --------------------------------------------------------------------------
    "PD_CC_OVERVOLTAGE": (CRITICAL, "pd", "Over-voltage on the USB-C CC lines.", "Unplug the cable: The cable or the adapter is faulty."),
    "PD_NO_CONTRACT": (INFO, "pd", "Adapter is not USB PD (5 V only).",
                       "Not supported: The Pi gets less power and charging is slow. Use a USB-C PD adapter that offers 9 V or 15 V at 3 A."),
    "PD_LOW_CONTRACT": (INFO, "pd", "Adapter offered less than 9 V.", "Use a PD adapter that offers 9 V or 15 V at 3 A."),
    "PD_CAPABILITY_MISMATCH": (WARNING, "pd", "Adapter cannot supply the current requested.", "Use a PD adapter that offers 9 V or 15 V at 3 A."),
    "PD_CONFIG_MISMATCH": (WARNING, "pd", "USB-C controller PDO settings differ from the factory settings.",
                           "Run ups.restore_pd_defaults(). If the fault returns after a restart, contact PinGoblin support."),
    # ---- battery, inferred -----------------------------------------------------------
    "BAT_ABSENT": (CRITICAL, "inferred", "No battery detected.",
                   "Plug the pack's XT30 lead into J3, switch the pack on and check its cells are fitted. A pack that is switched off, has tripped its protection or temperature cut-off, or has a blown fuse also reads as absent."),
    "BAT_WIRING_FAULT": (CRITICAL, "inferred", "Battery reads like a single cell or a reversed cell.",
                         "Check both cells in the pack are fitted the right way round. Charging is stopped."),
    "BAT_DEEPLY_DISCHARGED": (WARNING, "inferred", "Battery is below 6.0 V (deeply discharged).",
                              "Leave the adapter connected. If the battery does not recover within an hour, replace both cells."),
    "BAT_LOW": (WARNING, "inferred", "Battery low.", "Connect the adapter."),
    "BAT_CRITICAL": (CRITICAL, "inferred", "Battery critically low: Shut down now.", "Connect the adapter."),
    "BAT_CHARGE_BLOCKED": (WARNING, "inferred", "Charging has stopped before the battery is full.",
                           "The pack's protection has blocked charging: One cell reached 4.25 V, so the cells are out "
                           "of balance. Check the cells in the pack."),
    "BAT_IMBALANCE_SUSPECTED": (WARNING, "inferred", "Cells appear to be out of balance.",
                                "Charging repeatedly stops early. Balancing corrects small differences over several "
                                "charges. If it persists, replace both cells with a matched pair."),
    "BAT_EARLY_CUTOFF": (WARNING, "inferred", "Power was lost on battery while the pack still had charge.",
                         "One cell may be weak, or the load exceeded the pack's protection limit. Check the cells."),
    "BAT_HIGH_RESISTANCE": (WARNING, "inferred", "Battery path resistance is high.",
                            "Clean the pack's cell contacts and check the pack cable and connectors. "
                            "A gradual rise means the cells are ageing."),
    "BAT_CAPACITY_LOW": (WARNING, "inferred", "Measured battery capacity is well below the rated capacity.",
                         "The cells are worn, or cell_capacity_mah is set too high."),
    "BAT_PARALLEL_CELL_MISSING": (WARNING, "inferred", "Set for a QUAD pack (cells_parallel=2), but the battery behaves like a DUAL pack.",
                                  "Check that all four cells are fitted, or set cells_parallel=1."),
    "BAT_SELF_DISCHARGE": (WARNING, "inferred", "Battery needs recharging unusually often while on the adapter.",
                           "A cell may be leaking charge. Replace both cells if it persists."),
    # ---- adapter / output, inferred --------------------------------------------------
    "ADAPTER_INSUFFICIENT": (WARNING, "inferred", "Running partly from battery while the adapter is connected.",
                             "The adapter cannot carry the load. Use a USB-C PD adapter that offers 15 V at 3 A."),
    "CABLE_RESISTANCE_HIGH": (WARNING, "inferred", "High voltage drop in the USB-C cable or connector.",
                              "Use a shorter or better USB-C cable (rated 3 A or 5 A)."),
    "OUTPUT_OVERLOAD": (WARNING, "inferred", "Output power is near the 25 W limit.", "Reduce the load on the Pi and its USB ports."),
    "BOARD_TS_FAULT": (WARNING, "inferred", "Charger temperature-sense input is out of range: Charging is blocked.",
                       "The board needs repair: Contact PinGoblin support."),
    "BOARD_HOT": (WARNING, "inferred", "Charger temperature is high.", "Improve airflow around the HAT."),
    "BOARD_OVERHEAT": (CRITICAL, "inferred", "Charger temperature is very high.", "Shut the Pi down and improve cooling around the HAT."),
    # ---- Pi --------------------------------------------------------------------------
    "PI_UNDERVOLTAGE": (WARNING, "pi", "The Pi reports under-voltage on its 5 V input.",
                        "Remove USB devices from the Pi. If it returns, use a USB-C PD adapter that offers 15 V at 3 A."),
    "PI_UNDERVOLTAGE_OCCURRED": (INFO, "pi", "The Pi has seen under-voltage since boot.", ""),
    "OUTPUT_5V_FAULT": (CRITICAL, "inferred", "5 V output is low while the battery/adapter rail is healthy.",
                        "Remove USB devices and accessories from the Pi. If the fault returns with only the Pi connected, contact PinGoblin support."),
    "PI_EXTERNAL_SUPPLY": (INFO, "inferred", "The Pi appears to be powered from its own USB-C supply.",
                           "The UPS HAT+ is not carrying the load. Remove the Pi's own supply to get battery backup."),
}
"""Every fault code: `{code: (severity, source, message, advice)}`. See [Fault codes](../faults.md)."""


class Fault:
    """One active or transient fault.

    The severity, source, message and advice come from
    [`CATALOGUE`][ups_hat.faults.CATALOGUE]. An unknown code is treated as a warning with
    source `inferred`.

    Args:
        code: Fault code, for example `"BAT_LOW"`.
        data: Measurements that explain the fault, for example `{"soc": 12.5}`.
        transient: The fault appeared and cleared between two polls.
        since: Monotonic time (s) when the fault first became active.

    Attributes:
        code (str): Fault code.
        severity (int): 0 = info, 1 = warning, 2 = critical.
        source (str): `charger`, `pd`, `bus`, `inferred` or `pi`.
        message (str): One-line description.
        advice (str): What the user should do; may be empty.
        data (dict): Measurements that explain the fault.
        transient (bool): The fault came and went between two polls.
        since (float | None): Monotonic time (s) when it became active.

    Example:
        ```python
        for fault in ups.poll().faults:
            print(fault.code, fault.severity_name, fault.advice)
        ```
    """

    def __init__(self, code, data=None, transient=False, since=None):
        sev, src, msg, adv = CATALOGUE.get(code, (WARNING, "inferred", code, ""))
        self.code = code
        self.severity = sev
        self.source = src
        self.message = msg
        self.advice = adv
        self.data = data or {}
        self.transient = transient
        self.since = since

    @property
    def severity_name(self):
        """Severity as text: `"info"`, `"warning"` or `"critical"`.

        Example:
            ```python
            print(fault.severity_name)               # "warning"
            ```
        """
        return SEVERITY_NAMES[self.severity]

    def to_dict(self):
        """Convert to a JSON-serialisable dictionary.

        Returns:
            The fault's attributes, with the severity as text.

        Example:
            ```python
            print(fault.to_dict())
            ```
        """
        return {"code": self.code, "severity": self.severity_name, "source": self.source,
                "message": self.message, "advice": self.advice, "data": self.data,
                "transient": self.transient, "since": self.since}

    def __repr__(self):
        return "Fault({}, {}{})".format(self.code, self.severity_name, ", transient" if self.transient else "")

    def __str__(self):
        extra = ""
        if self.data:
            extra = " (" + ", ".join("{}={}".format(k, _fmt(self.data[k])) for k in sorted(self.data)) + ")"
        return "[{}] {}: {}{}".format(self.severity_name.upper(), self.code, self.message, extra)


def _fmt(v):
    if isinstance(v, float):
        return "{:.3g}".format(v)
    return str(v)
