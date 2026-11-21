"""High-level interface to the UPS HAT+ (Rev D and later)."""

import json

from . import bq25798 as bq
from .bq25798 import BQ25798
from .stusb4500 import STUSB4500
from .battery import BatteryMonitor
from .faults import Fault, CRITICAL, WARNING, INFO
from .bus import BusError, DeviceNotFound, NotSupported, UPSError, open_bus
from ._compat import now_s, wall_time, clamp, sleep_ms

# Factory USB-PD sink configuration (written in the test jig).
FACTORY_PDOS = ((5.0, 3.0), (9.0, 3.0), (15.0, 3.0))
STANDARD_PD_VOLTAGES = (5.0, 9.0, 12.0, 15.0, 20.0)

# Board limits
CHARGE_VOLTAGE_RANGE = (7.0, 8.4)      # 3.5-4.2 V per cell
CHARGE_CURRENT_MAX = 3.0
INPUT_CURRENT_MAX = 3.0                # USB-C cable/contract limit
OUTPUT_POWER_LIMIT = 25.5              # 5.1 V x 5 A
CHARGER_EFFICIENCY = 0.95
OUTPUT_EFFICIENCY = 0.93


class Snapshot:
    """Everything measured or worked out in one :meth:`UPS.poll`."""

    def __init__(self):
        self.time = None
        self.wall_time = None
        self.charger_ok = False
        self.pd_ok = False
        self.adc = None
        self.vbus = self.ibus = self.vbat = self.ibat = self.vsys = self.tdie = None
        self.ts_pct = None
        self.status = {}
        self.charger_faults = []
        self.flags = {"charger": [], "fault": []}
        self.adapter_present = False
        self.power_good = False
        self.on_battery = False
        self.charging = False
        self.charge_state = None
        self.charge_state_text = ""
        self.battery_present = False
        self.soc = None
        self.remaining_mah = None
        self.capacity_mah = None
        self.time_to_empty_h = None
        self.time_to_full_h = None
        self.battery_resistance = None
        self.input_power = None
        self.battery_power = None
        self.output_power = None
        self.pd = {}
        self.contract = None
        self.contract_voltage = None
        self.contract_current = None
        self.pi = {}
        self.faults = []
        self.new_faults = []
        self.cleared_faults = []
        self.should_shutdown = False

    def fault_codes(self):
        return [f.code for f in self.faults]

    def worst_severity(self):
        return max([f.severity for f in self.faults] or [-1])

    def to_dict(self):
        keys = ("time", "wall_time", "charger_ok", "pd_ok", "vbus", "ibus", "vbat", "ibat", "vsys", "tdie", "ts_pct",
                "adapter_present", "power_good", "on_battery", "charging", "charge_state", "charge_state_text",
                "battery_present", "soc", "remaining_mah", "capacity_mah", "time_to_empty_h", "time_to_full_h",
                "battery_resistance", "input_power", "battery_power", "output_power", "contract_voltage",
                "contract_current", "should_shutdown")
        d = {k: getattr(self, k) for k in keys}
        d["status"] = self.status
        d["charger_faults"] = self.charger_faults
        d["flags"] = self.flags
        d["pd"] = self.pd
        d["pi"] = self.pi
        d["faults"] = [f.to_dict() for f in self.faults]
        return d


class UPS:
    """The UPS HAT+.

    Parameters
    ----------
    i2c : machine.I2C-like object, optional
        Defaults to ``/dev/i2c-1`` on Linux. Required on MicroPython.
    cells_parallel : 1 or 2
        2S1P (two cells) or 2S2P (four cells).
    cell_capacity_mah : float
        Rated capacity of one cell.
    charge_voltage : float
        Pack charge voltage, 7.0-8.4 V. 8.2 V (4.10 V/cell) is the default for long life.
    charge_current : float, optional
        Default 1.5 A for 2S1P, 2.0 A for 2S2P.
    ship_fet : bool
        True when the board has the SDRV ship FET fitted (needed for power_off/ship mode).
    state_file : str, optional
        Where to keep learned battery data between runs (JSON). None = keep in memory only.
    low_battery_soc, low_battery_voltage : float
        Below either (on battery) ``should_shutdown`` becomes True.
    auto_configure : bool
        Apply the charger settings now, and re-apply them if the charger resets.
    protect : bool
        Stop charging when the battery reads like a wiring fault, and resume when it clears.
    pi_monitor : bool
        Read the Pi 5 supply state through vcgencmd when available.
    """

    def __init__(self, i2c=None, cells_parallel=1, cell_capacity_mah=3000.0, charge_voltage=8.2,
                 charge_current=None, ship_fet=True, state_file=None, low_battery_soc=5.0,
                 low_battery_voltage=6.2, auto_configure=True, protect=True, pi_monitor=True,
                 bus=1):
        if cells_parallel not in (1, 2):
            raise ValueError("cells_parallel must be 1 or 2")
        self.i2c = i2c if i2c is not None else open_bus(bus)
        self.cells_parallel = cells_parallel
        self.target_charge_voltage = clamp(charge_voltage, *CHARGE_VOLTAGE_RANGE)
        if charge_current is None:
            charge_current = 1.5 if cells_parallel == 1 else 2.0
        self.target_charge_current = clamp(charge_current, 0.1, CHARGE_CURRENT_MAX)
        self.ship_fet = ship_fet
        self.state_file = state_file
        self.low_battery_soc = low_battery_soc
        self.low_battery_voltage = low_battery_voltage
        self.auto_configure = auto_configure
        self.protect = protect

        self.charger = None
        self.pd = None
        self._connect()

        self.battery = BatteryMonitor(2, cells_parallel, cell_capacity_mah, self.target_charge_voltage / 2)
        self.pi = None
        if pi_monitor:
            try:
                from .pimon import PiPower
                p = PiPower()
                self.pi = p if p.available else None
            except Exception:
                self.pi = None

        self._active = {}          # code -> Fault
        self._timers = {}          # debounce: code -> first time condition seen
        self._callbacks = []
        self._clear_callbacks = []
        self._charge_disabled_by_protect = False
        self._charging_wanted = True
        self._last_config_check = None
        self._last_pi_check = None
        self._pi_cache = {}
        self._last_pd_check = None
        self._pd_config_ok = True
        self._prev = None
        self._charge_stop_events = 0
        self._last_done_time = None
        self._recharge_intervals = []
        self._was_done = False
        self._reset_detected_at = None
        self._boot_events = []
        self._last_save = None
        self._low_battery_shutdown = False
        self._last_contract_raw = None

        self._load_state()
        if auto_configure and self.charger is not None:
            self.configure()

    # ---- connection ------------------------------------------------------------------
    def _connect(self):
        try:
            self.charger = BQ25798(self.i2c)
        except (BusError, DeviceNotFound):
            self.charger = None
        try:
            self.pd = STUSB4500(self.i2c)
        except (BusError, DeviceNotFound):
            self.pd = None

    def _need_charger(self):
        if self.charger is None:
            self._connect()
        if self.charger is None:
            raise DeviceNotFound("BQ25798 charger not found at 0x6B")
        return self.charger

    def _need_pd(self):
        if self.pd is None:
            self._connect()
        if self.pd is None:
            raise DeviceNotFound("STUSB4500 not found at 0x28")
        return self.pd

    # ---- configuration ---------------------------------------------------------------
    def configure(self):
        """Apply the board's charger settings. Safe to call at any time."""
        c = self._need_charger()
        c.watchdog_s = 0                           # settings hold without host kicks
        c.adc_enable(True, continuous=True, bits=15)
        c.ibat_discharge_sensing = True            # IBAT also on battery-only
        c.charge_voltage = self.target_charge_voltage
        c.charge_current = self.target_charge_current
        if self.ship_fet:
            c.sfet_present = True                  # unlocks SDRV_CTRL and QON
        if not self._charge_disabled_by_protect:
            c.charge_enabled = self._charging_wanted
        self._last_config_check = now_s()

    def _settings_lost(self):
        c = self.charger
        if abs(c.charge_voltage - self.target_charge_voltage) > 0.015:
            return True
        if c.watchdog_s != 0 or not c.adc_enabled:
            return True
        if self.ship_fet and not c.sfet_present:
            return True
        return False

    def sync_input_current_limit(self):
        """Set the charger input current limit from the USB-C contract (PD) or Rp advertisement."""
        c = self._need_charger()
        limit = None
        if self.pd is not None:
            try:
                k = self.pd.contract
                if k.valid and k.operating_current > 0:
                    limit = k.operating_current
                else:
                    st = self.pd.status()
                    cc = st["cc2"] if st["orientation"] == "CC2" else st["cc1"]
                    limit = {"3.0 A": 3.0, "1.5 A": 1.5}.get(cc, 0.5)
            except BusError:
                limit = None
        if limit is None:
            return None
        limit = clamp(limit, 0.1, INPUT_CURRENT_MAX)
        c.input_current_limit = limit
        return limit

    # ---- charging --------------------------------------------------------------------
    @property
    def charging_enabled(self):
        return self._need_charger().charge_enabled

    def enable_charging(self, on=True):
        self._charging_wanted = bool(on)
        if not self._charge_disabled_by_protect:
            self._need_charger().charge_enabled = self._charging_wanted

    def set_charge_voltage(self, volts):
        """Pack charge voltage, 7.0-8.4 V."""
        self.target_charge_voltage = clamp(volts, *CHARGE_VOLTAGE_RANGE)
        self._need_charger().charge_voltage = self.target_charge_voltage
        self.battery.full_cell_voltage = self.target_charge_voltage / 2

    def set_charge_current(self, amps):
        self.target_charge_current = clamp(amps, 0.1, CHARGE_CURRENT_MAX)
        self._need_charger().charge_current = self.target_charge_current

    def set_input_current_limit(self, amps):
        self._need_charger().input_current_limit = clamp(amps, 0.1, INPUT_CURRENT_MAX)

    # ---- power control ---------------------------------------------------------------
    def _need_ship_fet(self):
        if not self.ship_fet:
            raise NotSupported("power off needs the SDRV ship FET (board built with ship_fet=False)")
        c = self._need_charger()
        c.sfet_present = True
        return c

    def ship_mode(self, delay=False):
        """Disconnect the battery. Wakes on QON (SW1) or when an adapter is plugged in.
        Ignored by the charger while an adapter is connected."""
        self._save_state(clean=True)
        self._need_ship_fet().set_ship_fet_control(bq.SDRV_SHIP, delay)

    def shutdown_mode(self, delay=False):
        """Lowest-drain off state. Wakes only when an adapter is plugged in (not on SW1)."""
        self._save_state(clean=True)
        self._need_ship_fet().set_ship_fet_control(bq.SDRV_SHUTDOWN, delay)

    def system_reset(self, delay=False):
        """Briefly cut and restore power to the Pi (power cycle)."""
        self._save_state(clean=True)
        self._need_ship_fet().set_ship_fet_control(bq.SDRV_SYSTEM_RESET, delay)

    def power_off(self, low_battery=None):
        """Final step of a Pi shutdown (call from systemd-shutdown on poweroff/halt).

        - No adapter: ship mode, the board goes dark.
        - Adapter present and this was a low-battery shutdown: system reset, so the Pi
          boots again on mains instead of sitting halted.
        - Adapter present otherwise: nothing (the Pi halts; the board stays on).

        Returns "ship", "reset" or "none".
        """
        if low_battery is None:
            low_battery = self._low_battery_shutdown
        c = self._need_charger()
        st = c.status()
        if not st["VBUS_PRESENT"]:
            self.ship_mode(delay=False)
            return "ship"
        if low_battery:
            self.system_reset(delay=False)
            return "reset"
        self._save_state(clean=True)
        return "none"

    # ---- USB-C PD --------------------------------------------------------------------
    def renegotiate_pd(self):
        self._need_pd().renegotiate()

    def pd_config(self):
        """Sink PDOs in use (RAM) and stored in NVM."""
        pd = self._need_pd()
        ram = [(p.voltage, p.current) for p in pd.sink_pdos()]
        n, nvm = STUSB4500.decode_nvm_pdos(pd.read_nvm())
        return {"ram_count": pd.pdo_count, "ram": ram, "nvm_count": n, "nvm": nvm[:n]}

    def check_pd_config(self):
        """True when the sink PDOs match the factory configuration."""
        pd = self._need_pd()
        pdos = pd.sink_pdos()
        if len(pdos) != len(FACTORY_PDOS):
            return False
        for p, (v, a) in zip(pdos, FACTORY_PDOS):
            if abs(p.voltage - v) > 0.06 or abs(p.current - a) > 0.06:
                return False
        return True

    def restore_pd_defaults(self, write_nvm=False):
        """Load the factory PDOs into RAM and renegotiate. write_nvm=True also reprograms the
        NVM (factory/service use; limited write endurance)."""
        pd = self._need_pd()
        for i, (v, a) in enumerate(FACTORY_PDOS):
            pd.set_sink_pdo(i + 1, v, a)
        pd.pdo_count = len(FACTORY_PDOS)
        if write_nvm:
            sectors = pd.read_nvm()
            pd.write_nvm(STUSB4500.encode_nvm_pdos(sectors, FACTORY_PDOS, len(FACTORY_PDOS)), confirm=True)
        pd.renegotiate()

    # ---- callbacks -------------------------------------------------------------------
    def on_fault(self, fn):
        """Call fn(fault) when a fault becomes active (or a transient one is seen)."""
        self._callbacks.append(fn)
        return fn

    def on_clear(self, fn):
        """Call fn(fault) when an active fault clears."""
        self._clear_callbacks.append(fn)
        return fn

    @property
    def faults(self):
        return list(self._active.values())

    # ---- polling ---------------------------------------------------------------------
    def _held(self, code, cond, t, seconds):
        """Debounce: True once cond has held for `seconds`."""
        if not cond:
            self._timers.pop(code, None)
            return False
        first = self._timers.get(code)
        if first is None:
            self._timers[code] = t
            return seconds <= 0
        return t - first >= seconds

    def poll(self):
        """Read everything, update the battery model, diagnose, and return a :class:`Snapshot`.
        Call every 1-5 s."""
        t = now_s()
        s = Snapshot()
        s.time = t
        s.wall_time = wall_time()
        found = []          # list of (code, data, transient)

        # --- charger ---
        c = self.charger
        if c is None:
            self._connect()
            c = self.charger
        if c is not None:
            try:
                adc = c.read_adc()
                st = c.status()
                s.charger_faults = c.faults()
                s.flags = c.read_flags()
                s.charger_ok = True
                s.adc = adc
                s.vbus, s.ibus, s.vbat, s.ibat, s.vsys, s.tdie = adc.vbus, adc.ibus, adc.vbat, adc.ibat, adc.vsys, adc.tdie
                s.ts_pct = adc.ts_pct
                s.status = st
            except BusError:
                self.charger = None
        if not s.charger_ok:
            found.append(("BUS_CHARGER_MISSING", None, False))

        # --- PD ---
        if self.pd is None and c is not None:
            try:
                self.pd = STUSB4500(self.i2c)
            except (BusError, DeviceNotFound):
                self.pd = None
        if self.pd is not None:
            try:
                s.pd = self.pd.status()
                k = self.pd.contract
                s.contract = k
                s.pd["contract"] = repr(k)
                s.pd["events"] = self.pd.monitoring_events()
                s.pd_ok = True
                if k.raw != self._last_contract_raw and self.charger is not None and self.auto_configure:
                    self._last_contract_raw = k.raw
                    try:
                        self.sync_input_current_limit()
                    except (BusError, DeviceNotFound):
                        pass
                if self._last_pd_check is None or t - self._last_pd_check > 3600:
                    self._pd_config_ok = self.check_pd_config()
                    self._last_pd_check = t
            except BusError:
                self.pd = None
        if not s.pd_ok:
            found.append(("BUS_PD_MISSING", None, False))

        if s.charger_ok:
            self._derive(s, t)
            self._check_settings(s, t, found)
            self._diagnose_charger(s, t, found)
            self._diagnose_battery(s, t, found)
            self._diagnose_ts(s, t, found)
            self._diagnose_power(s, t, found)
        if s.pd_ok:
            self._diagnose_pd(s, t, found)
        self._diagnose_pi(s, t, found)
        for code, data in self._boot_events:
            found.append((code, data, False))

        self._update_faults(s, found, t)
        self._prev = s
        if self.state_file and (self._last_save is None or t - self._last_save > 300):
            self._save_state()
        return s

    def _derive(self, s, t):
        st = s.status
        s.adapter_present = st.get("VBUS_PRESENT", False)
        s.power_good = st.get("POWER_GOOD", False)
        s.charge_state = st.get("charge_state")
        s.charge_state_text = st.get("charge_state_text", "")
        s.charging = s.charge_state in (bq.CHG_TRICKLE, bq.CHG_PRECHARGE, bq.CHG_FAST, bq.CHG_TAPER, bq.CHG_TOPOFF)
        s.on_battery = not s.power_good
        s.battery_present = st.get("VBAT_PRESENT", False) and s.vbat > 3.0
        done = s.charge_state == bq.CHG_DONE and s.adapter_present
        self.battery.update(t, s.vbat, s.ibat, charge_done=done, present=s.battery_present)
        b = self.battery
        s.soc = b.soc if s.battery_present else None
        s.remaining_mah = b.remaining_mah if s.battery_present else None
        s.capacity_mah = b.capacity_mah
        s.battery_resistance = b.resistance
        s.time_to_empty_h = b.time_to_empty_h(s.ibat)
        s.time_to_full_h = b.time_to_full_h(s.ibat) if s.charging else None
        s.input_power = s.vbus * s.ibus if s.adapter_present else 0.0
        s.battery_power = -s.vbat * s.ibat           # > 0 when the battery supplies power
        p_sys = s.input_power * CHARGER_EFFICIENCY + s.battery_power
        s.output_power = max(0.0, p_sys * OUTPUT_EFFICIENCY - 0.15)
        k = s.contract
        if k is not None and k.valid and s.adapter_present:
            s.contract_current = k.operating_current
            s.contract_voltage = _nearest_pd_voltage(s.vbus)
        if s.on_battery and s.battery_present:
            if (s.soc is not None and s.soc <= self.low_battery_soc) or s.vbat <= self.low_battery_voltage:
                s.should_shutdown = True
                self._low_battery_shutdown = True
        elif s.power_good:
            self._low_battery_shutdown = False

    def _check_settings(self, s, t, found):
        if self.auto_configure and (self._last_config_check is None or t - self._last_config_check >= 60
                                    or "WATCHDOG_EXPIRED" in s.flags["charger"]):
            self._last_config_check = t
            try:
                if self._settings_lost():
                    self.configure()
                    self._reset_detected_at = t
            except BusError:
                pass
        if self._reset_detected_at is not None and t - self._reset_detected_at < 600:
            found.append(("CHG_RESET_DETECTED", None, False))

    def _diagnose_charger(self, s, t, found):
        names = {"VBUS_OVP": "CHG_VBUS_OVP", "VBAT_OVP": "CHG_VBAT_OVP", "IBUS_OCP": "CHG_IBUS_OCP",
                 "IBAT_OCP": "CHG_IBAT_OCP", "CONVERTER_OCP": "CHG_CONVERTER_OCP", "VAC1_OVP": "CHG_VAC_OVP",
                 "VAC2_OVP": "CHG_VAC_OVP", "VSYS_SHORT": "CHG_VSYS_SHORT", "VSYS_OVP": "CHG_VSYS_OVP",
                 "THERMAL_SHUTDOWN": "CHG_THERMAL_SHUTDOWN", "IBAT_REGULATION": "CHG_IBAT_REGULATION"}
        active = set()
        for f in s.charger_faults:
            if f in names:
                active.add(names[f])
                found.append((names[f], None, False))
        for f in s.flags["fault"]:
            code = names.get(f)
            if code and code not in active:
                found.append((code, None, True))       # came and went since last poll
        st = s.status
        if st.get("CHARGE_TIMER_EXPIRED"):
            found.append(("CHG_TIMER_EXPIRED", None, False))
        if st.get("PRECHARGE_TIMER_EXPIRED"):
            found.append(("CHG_PRECHARGE_TIMER_EXPIRED", None, False))
        if st.get("TRICKLE_TIMER_EXPIRED"):
            found.append(("CHG_TRICKLE_TIMER_EXPIRED", None, False))
        if st.get("WATCHDOG_EXPIRED") or "WATCHDOG_EXPIRED" in s.flags["charger"]:
            found.append(("CHG_WATCHDOG_EXPIRED", None, not st.get("WATCHDOG_EXPIRED")))
        if st.get("THERMAL_REGULATION"):
            found.append(("CHG_THERMAL_REGULATION", {"tdie": s.tdie}, False))
        if st.get("POOR_SOURCE") or "POOR_SOURCE" in s.flags["charger"]:
            found.append(("CHG_POOR_SOURCE", None, not st.get("POOR_SOURCE")))
        lim = st.get("IINDPM") or st.get("VINDPM")
        if self._held("CHG_INPUT_LIMITED", lim and s.adapter_present, t, 30):
            found.append(("CHG_INPUT_LIMITED", {"iindpm": st.get("IINDPM"), "vindpm": st.get("VINDPM"),
                                                "ibus": s.ibus, "vbus": s.vbus}, False))

    def _diagnose_battery(self, s, t, found):
        c = self.charger
        vreg = self.target_charge_voltage
        b = self.battery
        # presence and wiring (only meaningful with an adapter: on battery we would not be running)
        if s.adapter_present:
            absent = not s.status.get("VBAT_PRESENT", False) or s.vbat < 2.5
            if self._held("BAT_ABSENT", absent, t, 5):
                found.append(("BAT_ABSENT", {"vbat": s.vbat}, False))
            wiring = 2.5 <= s.vbat < 4.6
            if self._held("BAT_WIRING_FAULT", wiring, t, 10):
                found.append(("BAT_WIRING_FAULT", {"vbat": s.vbat}, False))
                if self.protect and not self._charge_disabled_by_protect:
                    try:
                        c.charge_enabled = False
                        self._charge_disabled_by_protect = True
                    except BusError:
                        pass
            elif not wiring and self._charge_disabled_by_protect and s.vbat >= 4.6:
                try:
                    c.charge_enabled = self._charging_wanted
                    self._charge_disabled_by_protect = False
                except BusError:
                    pass
            if self._held("BAT_DEEPLY_DISCHARGED", 4.6 <= s.vbat < 6.0, t, 10):
                found.append(("BAT_DEEPLY_DISCHARGED", {"vbat": s.vbat}, False))

        # state of charge
        if s.on_battery and s.battery_present:
            if s.should_shutdown:
                found.append(("BAT_CRITICAL", {"soc": s.soc, "vbat": s.vbat}, False))
            elif s.soc is not None and s.soc <= 15:
                found.append(("BAT_LOW", {"soc": s.soc}, False))

        # charging blocked by the pack's HY2120 (charge FET off) or an open contact
        timers = s.status.get("CHARGE_TIMER_EXPIRED") or s.status.get("PRECHARGE_TIMER_EXPIRED") \
            or s.status.get("TRICKLE_TIMER_EXPIRED")
        blocked = (s.power_good and s.battery_present and self._charging_wanted
                   and not self._charge_disabled_by_protect and not timers and not s.charger_faults
                   and s.vbat >= 6.0 and s.vbat < vreg - 0.25 and abs(s.ibat) < 0.02
                   and not s.status.get("THERMAL_REGULATION"))
        if self._held("BAT_CHARGE_BLOCKED", blocked, t, 120):
            found.append(("BAT_CHARGE_BLOCKED", {"vbat": s.vbat}, False))
            if s.vbat > 7.6:
                found.append(("BAT_IMBALANCE_SUSPECTED", {"vbat": s.vbat, "reason": "charging stopped near full"}, False))

        # abrupt charge stop below full: one cell hit 4.25 V and the pack's HY2120 opened its charge FET
        p = self._prev
        if p is not None and p.charger_ok and p.charging and s.power_good:
            iterm = 0.2
            if p.ibat > max(0.3, 3 * iterm) and abs(s.ibat) < 0.05 and p.vbat < vreg - 0.15 \
                    and s.status.get("POWER_GOOD") and not s.charger_faults:
                self._charge_stop_events += 1
        if self._charge_stop_events >= 2:
            found.append(("BAT_IMBALANCE_SUSPECTED", {"early_stops": self._charge_stop_events}, False))

        # resistance, capacity
        r = b.resistance
        if r is not None:
            limit = 0.35 if self.cells_parallel == 1 else 0.22
            jump = b.resistance_baseline is not None and r > 1.8 * b.resistance_baseline
            if r > limit or jump:
                found.append(("BAT_HIGH_RESISTANCE", {"ohm": r, "baseline": b.resistance_baseline}, False))
        if b.learned_capacity_mah is not None:
            ratio = b.learned_capacity_mah / b.nominal_capacity_mah
            if self.cells_parallel == 2 and ratio < 0.6:
                found.append(("BAT_PARALLEL_CELL_MISSING", {"capacity_mah": b.learned_capacity_mah}, False))
            elif ratio < 0.7:
                found.append(("BAT_CAPACITY_LOW", {"capacity_mah": b.learned_capacity_mah,
                                                   "rated_mah": b.nominal_capacity_mah}, False))

        # recharge cycles on mains: frequent recharges mean self-discharge
        done = s.charge_state == bq.CHG_DONE
        if self._was_done and s.charging and s.adapter_present and s.output_power is not None:
            if self._last_done_time is not None:
                self._recharge_intervals = (self._recharge_intervals + [t - self._last_done_time])[-3:]
        if done and not self._was_done:
            self._last_done_time = t
        self._was_done = done
        iv = self._recharge_intervals
        if len(iv) >= 2 and max(iv[-2:]) < 6 * 3600:
            found.append(("BAT_SELF_DISCHARGE", {"hours_between_recharges": min(iv[-2:]) / 3600.0}, False))

    def _diagnose_ts(self, s, t, found):
        """No battery NTC on Rev D: R4 10k / R5 15k hold TS at 60 % of REGN (normal temperature).
        A cold/hot TS state can only mean the divider is damaged, which blocks charging."""
        st = s.status
        bad = any(st.get(f) for f in ("TS_COLD", "TS_COOL", "TS_WARM", "TS_HOT"))
        if s.ts_pct is not None and not (50.0 <= s.ts_pct <= 70.0):
            bad = True
        if self._held("BOARD_TS_FAULT", bad and s.battery_present, t, 5):
            found.append(("BOARD_TS_FAULT", {"ts_pct": s.ts_pct}, False))

    def _diagnose_power(self, s, t, found):
        if self._held("ADAPTER_INSUFFICIENT", s.power_good and s.ibat < -0.2, t, 30):
            found.append(("ADAPTER_INSUFFICIENT", {"ibat": s.ibat, "ibus": s.ibus}, False))
        if s.contract_voltage and s.ibus > 1.5:
            drop = s.contract_voltage - s.vbus
            r = drop / s.ibus
            if self._held("CABLE_RESISTANCE_HIGH", r > 0.25, t, 30):
                found.append(("CABLE_RESISTANCE_HIGH", {"ohm": r, "vbus": s.vbus, "ibus": s.ibus}, False))
        else:
            self._timers.pop("CABLE_RESISTANCE_HIGH", None)
        if self._held("OUTPUT_OVERLOAD", s.output_power > 0.95 * OUTPUT_POWER_LIMIT, t, 10):
            found.append(("OUTPUT_OVERLOAD", {"watts": s.output_power}, False))
        if s.tdie >= 105:
            found.append(("BOARD_OVERHEAT", {"tdie": s.tdie}, False))
        elif s.tdie >= 85:
            found.append(("BOARD_HOT", {"tdie": s.tdie}, False))

    def _diagnose_pd(self, s, t, found):
        pd = s.pd
        if pd.get("vpu_ovp"):
            found.append(("PD_CC_OVERVOLTAGE", None, False))
        k = s.contract
        attached = pd.get("attached") and pd.get("vbus_valid")
        if self._held("PD_NO_CONTRACT", attached and not (k and k.valid), t, 10):
            found.append(("PD_NO_CONTRACT", None, False))
        if k is not None and k.valid:
            if k.capability_mismatch:
                found.append(("PD_CAPABILITY_MISMATCH", {"current": k.operating_current}, False))
            if s.charger_ok and self._held("PD_LOW_CONTRACT", s.adapter_present and s.vbus < 8.0, t, 10):
                found.append(("PD_LOW_CONTRACT", {"vbus": s.vbus}, False))
        if not self._pd_config_ok:
            found.append(("PD_CONFIG_MISMATCH", None, False))

    def _diagnose_pi(self, s, t, found):
        if self.pi is None:
            return
        if self._last_pi_check is None or t - self._last_pi_check >= 10:
            self._last_pi_check = t
            self._pi_cache = {"throttled": self.pi.throttled(), "ext5v": self.pi.ext5v()}
        s.pi = self._pi_cache
        th = s.pi.get("throttled") or {}
        v5 = s.pi.get("ext5v")
        if th.get("under_voltage"):
            found.append(("PI_UNDERVOLTAGE", {"ext5v": v5}, False))
        elif th.get("under_voltage_occurred"):
            found.append(("PI_UNDERVOLTAGE_OCCURRED", None, False))
        if v5 is not None and s.charger_ok:
            low = v5 < 4.75 and s.vsys is not None and s.vsys > 6.5
            if self._held("OUTPUT_5V_FAULT", low, t, 5):
                found.append(("OUTPUT_5V_FAULT", {"ext5v": v5, "vsys": s.vsys}, False))
            ext = v5 >= 4.9 and s.output_power is not None and s.output_power < 0.8
            if self._held("PI_EXTERNAL_SUPPLY", ext, t, 60):
                found.append(("PI_EXTERNAL_SUPPLY", {"output_w": s.output_power}, False))

    def _update_faults(self, s, found, t):
        current = {}
        transient = []
        for code, data, is_transient in found:
            if is_transient:
                transient.append(Fault(code, data, transient=True, since=t))
                continue
            if code in current:
                if data:
                    current[code].data.update(data)
                continue
            old = self._active.get(code)
            f = Fault(code, data, since=old.since if old else t)
            current[code] = f
        new = [f for c, f in current.items() if c not in self._active] + transient
        cleared = [f for c, f in self._active.items() if c not in current]
        self._active = current
        s.faults = sorted(list(current.values()) + transient, key=lambda f: -f.severity)
        s.new_faults = new
        s.cleared_faults = cleared
        for f in new:
            for fn in self._callbacks:
                fn(f)
        for f in cleared:
            for fn in self._clear_callbacks:
                fn(f)

    # ---- monitoring loop -------------------------------------------------------------
    def run(self, interval_s=2.0, callback=None, count=None):
        """Poll forever (or `count` times), calling callback(snapshot) each time."""
        n = 0
        while count is None or n < count:
            s = self.poll()
            if callback is not None:
                callback(s)
            n += 1
            sleep_ms(int(interval_s * 1000))

    # ---- state persistence -----------------------------------------------------------
    def _load_state(self):
        if not self.state_file:
            return
        try:
            with open(self.state_file) as f:
                d = json.load(f)
        except (OSError, ValueError):
            return
        self.battery.from_dict(d.get("battery", {}), restore_soc=True)
        self._charge_stop_events = d.get("charge_stop_events", 0)
        last = d.get("last", {})
        # Power lost on battery with charge left: early cut-off.
        if last and last.get("on_battery") and not d.get("clean_shutdown"):
            v = last.get("vbat") or 0
            if v > 6.6:
                self._boot_events.append(("BAT_EARLY_CUTOFF", {"last_vbat": v, "last_soc": last.get("soc")}))
        if not d.get("clean_shutdown") and last.get("on_battery"):
            self.battery.anchored = False    # SoC history unreliable after a power loss

    def _save_state(self, clean=False):
        if not self.state_file:
            return
        p = self._prev
        d = {"battery": self.battery.to_dict(), "charge_stop_events": self._charge_stop_events,
             "clean_shutdown": clean, "saved": wall_time(),
             "last": {"on_battery": p.on_battery, "vbat": p.vbat, "soc": p.soc} if p is not None and p.charger_ok else {}}
        try:
            tmp = self.state_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(d, f)
            try:
                import os
                os.rename(tmp, self.state_file)
            except Exception:
                with open(self.state_file, "w") as f:
                    json.dump(d, f)
        except OSError:
            return
        self._last_save = now_s()

    def save_state(self, clean=False):
        """Write learned battery data to state_file. Pass clean=True when the Pi is shutting
        down normally, so the next start does not report BAT_EARLY_CUTOFF."""
        self._save_state(clean)

    def acknowledge(self, code):
        """Clear a latched inferred fault (BAT_EARLY_CUTOFF, BAT_IMBALANCE_SUSPECTED,
        BAT_SELF_DISCHARGE, CHG_RESET_DETECTED) after the user has dealt with it."""
        self._boot_events = [e for e in self._boot_events if e[0] != code]
        if code == "BAT_IMBALANCE_SUSPECTED":
            self._charge_stop_events = 0
        if code == "BAT_SELF_DISCHARGE":
            self._recharge_intervals = []
        if code == "CHG_RESET_DETECTED":
            self._reset_detected_at = None

    def new_cells_fitted(self):
        """Call after replacing the cells: forget learned capacity, resistance and history."""
        self.battery.reset_learning()
        self.battery.soc = None
        self.battery.anchored = False
        self._charge_stop_events = 0
        self._recharge_intervals = []
        self._boot_events = []
        self._save_state()

    # ---- reporting -------------------------------------------------------------------
    def report(self, s=None):
        """Human-readable multi-line status."""
        s = s or self.poll()
        L = []
        if not s.charger_ok:
            L.append("Charger not responding.")
        else:
            src = "adapter" if s.power_good else "battery"
            L.append("Power source : {}".format(src))
            L.append("Input        : {:.2f} V  {:.2f} A  ({:.1f} W)".format(s.vbus, s.ibus, s.input_power))
            if s.contract_voltage:
                L.append("USB-C PD     : {:.0f} V contract, {:.2f} A".format(s.contract_voltage, s.contract_current))
            soc = "--" if s.soc is None else "{:.0f} %".format(s.soc)
            L.append("Battery      : {:.2f} V  {:+.2f} A  {}  ({})".format(s.vbat, s.ibat, soc, s.charge_state_text))
            if s.time_to_empty_h:
                L.append("Time to empty: {:.1f} h".format(s.time_to_empty_h))
            if s.time_to_full_h:
                L.append("Time to full : {:.1f} h".format(s.time_to_full_h))
            L.append("System rail  : {:.2f} V".format(s.vsys))
            L.append("Output (est.): {:.1f} W".format(s.output_power))
            L.append("Charger temp : {:.1f} C".format(s.tdie))
            if s.battery_resistance:
                L.append("Batt. path R : {:.0f} mOhm".format(s.battery_resistance * 1000))
            L.append("Capacity     : {:.0f} mAh ({})".format(s.capacity_mah,
                     "measured" if self.battery.learned_capacity_mah else "rated"))
        if s.pi.get("ext5v") is not None:
            L.append("Pi 5 V input : {:.2f} V".format(s.pi["ext5v"]))
        if s.faults:
            L.append("Faults:")
            for f in s.faults:
                L.append("  " + str(f))
                if f.advice:
                    L.append("    -> " + f.advice)
        else:
            L.append("Faults       : none")
        return "\n".join(L)


def _nearest_pd_voltage(v):
    best = None
    for p in STANDARD_PD_VOLTAGES:
        if best is None or abs(p - v) < abs(best - v):
            best = p
    return best if abs(best - v) < 1.5 else None
