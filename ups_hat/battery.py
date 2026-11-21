"""Battery state estimation for the 2S pack: state of charge, capacity and resistance.

State of charge is counted from IBAT (coulomb counting), re-anchored to 100 %
when the charger reports charge done and corrected from the open-circuit
voltage after the pack has rested. 100 % means "full at the configured charge
voltage" (8.20 V by default), so capacity figures are usable capacity.
"""

from ._compat import clamp

# Typical NMC/NCA 18650 open-circuit voltage per cell (V) at 0..100 % in 5 % steps.
OCV_TABLE = (3.27, 3.61, 3.69, 3.71, 3.73, 3.75, 3.77, 3.79, 3.80, 3.82, 3.84,
             3.85, 3.87, 3.91, 3.95, 3.98, 4.02, 4.08, 4.11, 4.15, 4.20)


def soc_from_ocv(cell_v):
    """Percent of a 4.20 V-full cell from its resting voltage."""
    t = OCV_TABLE
    if cell_v <= t[0]:
        return 0.0
    if cell_v >= t[-1]:
        return 100.0
    for i in range(1, len(t)):
        if cell_v <= t[i]:
            return (i - 1 + (cell_v - t[i - 1]) / (t[i] - t[i - 1])) * 5.0
    return 100.0


class BatteryMonitor:
    REST_CURRENT = 0.05       # A, below this the pack is "resting"
    REST_TIME = 1800.0        # s of rest before trusting OCV
    IR_STEP = 0.3             # A, minimum current step for a resistance sample
    IR_MAX_DT = 5.0           # s between samples for a resistance sample

    def __init__(self, series=2, parallel=1, cell_capacity_mah=3000.0, full_cell_voltage=4.10):
        self.series = series
        self.parallel = parallel
        self.cell_capacity_mah = cell_capacity_mah
        self.full_cell_voltage = full_cell_voltage
        self.soc = None               # %
        self.remaining_mah = None
        self.learned_capacity_mah = None
        self.resistance = None        # ohm, whole battery path
        self.resistance_baseline = None
        self._ir_samples = []
        self._last = None             # (t, v, i)
        self._rest_since = None
        self._discharged_since_full = None
        self.cycle_mah = 0.0          # total discharged mAh (cycle counting)
        self.anchored = False         # True once SoC has a solid reference

    # ---- derived ---------------------------------------------------------------------
    @property
    def nominal_capacity_mah(self):
        """Rated capacity scaled to the configured full voltage."""
        frac = soc_from_ocv(self.full_cell_voltage) / 100.0
        return self.cell_capacity_mah * self.parallel * frac

    @property
    def capacity_mah(self):
        return self.learned_capacity_mah or self.nominal_capacity_mah

    @property
    def cycles(self):
        return self.cycle_mah / self.capacity_mah if self.capacity_mah else 0.0

    def soc_from_voltage(self, pack_v):
        cell = pack_v / self.series
        full = soc_from_ocv(self.full_cell_voltage)
        return clamp(soc_from_ocv(cell) / full * 100.0, 0.0, 100.0)

    # ---- updates ---------------------------------------------------------------------
    def update(self, t, vbat, ibat, charge_done=False, present=True):
        """Feed one measurement. t in seconds (monotonic), ibat > 0 charging."""
        if not present:
            self._last = None
            return
        cap = self.capacity_mah
        if self.soc is None:
            self.soc = self.soc_from_voltage(vbat)
            self.remaining_mah = cap * self.soc / 100.0

        if self._last is not None:
            t0, v0, i0 = self._last
            dt = t - t0
            if 0 < dt < 600:
                dmah = (i0 + ibat) / 2.0 * 1000.0 * dt / 3600.0
                self.remaining_mah = clamp(self.remaining_mah + dmah, 0.0, cap)
                if dmah < 0:
                    self.cycle_mah += -dmah
                    if self._discharged_since_full is not None:
                        self._discharged_since_full += -dmah
                self.soc = self.remaining_mah / cap * 100.0
                if dt <= self.IR_MAX_DT and abs(ibat - i0) >= self.IR_STEP:
                    r = (vbat - v0) / (ibat - i0)
                    if 0.005 < r < 2.0:
                        self._add_ir(r)

        if charge_done:
            self.soc = 100.0
            self.remaining_mah = cap
            self.anchored = True
            self._discharged_since_full = 0.0

        if abs(ibat) < self.REST_CURRENT:
            if self._rest_since is None:
                self._rest_since = t
            elif t - self._rest_since >= self.REST_TIME and not charge_done:
                self._ocv_correct(vbat)
                self._rest_since = t   # at most one correction per rest period
        else:
            self._rest_since = None
        self._last = (t, vbat, ibat)

    def _ocv_correct(self, vbat):
        ocv_soc = self.soc_from_voltage(vbat)
        if self._discharged_since_full is not None and self._discharged_since_full > 0.3 * self.nominal_capacity_mah \
                and ocv_soc < 70:
            est = self._discharged_since_full / (1.0 - ocv_soc / 100.0)
            if 0.2 * self.nominal_capacity_mah < est < 1.5 * self.nominal_capacity_mah:
                self.learned_capacity_mah = est if self.learned_capacity_mah is None \
                    else 0.7 * self.learned_capacity_mah + 0.3 * est
            self._discharged_since_full = None
        if not self.anchored or abs(ocv_soc - self.soc) > 10:
            self.soc = ocv_soc
            self.remaining_mah = self.capacity_mah * ocv_soc / 100.0
            self.anchored = True

    def _add_ir(self, r):
        self.resistance = r if self.resistance is None else 0.8 * self.resistance + 0.2 * r
        if self.resistance_baseline is None:
            self._ir_samples.append(r)
            if len(self._ir_samples) >= 20:
                s = sorted(self._ir_samples)
                self.resistance_baseline = s[len(s) // 2]
                self._ir_samples = []

    def reset_learning(self):
        """Forget learned capacity and resistance (call after fitting new cells)."""
        self.learned_capacity_mah = None
        self.resistance = None
        self.resistance_baseline = None
        self._ir_samples = []
        self.cycle_mah = 0.0

    def time_to_empty_h(self, ibat):
        if ibat >= -0.02 or self.remaining_mah is None:
            return None
        return self.remaining_mah / (-ibat * 1000.0)

    def time_to_full_h(self, ibat):
        if ibat <= 0.02 or self.remaining_mah is None:
            return None
        return (self.capacity_mah - self.remaining_mah) / (ibat * 1000.0) * 1.15  # CV tail

    # ---- persistence -----------------------------------------------------------------
    def to_dict(self):
        return {"soc": self.soc, "remaining_mah": self.remaining_mah, "anchored": self.anchored,
                "learned_capacity_mah": self.learned_capacity_mah, "resistance": self.resistance,
                "resistance_baseline": self.resistance_baseline, "cycle_mah": self.cycle_mah,
                "discharged_since_full": self._discharged_since_full}

    def from_dict(self, d, restore_soc=True):
        self.learned_capacity_mah = d.get("learned_capacity_mah")
        self.resistance = d.get("resistance")
        self.resistance_baseline = d.get("resistance_baseline")
        self.cycle_mah = d.get("cycle_mah") or 0.0
        if restore_soc and d.get("soc") is not None:
            self.soc = d["soc"]
            self.remaining_mah = d.get("remaining_mah")
            self.anchored = bool(d.get("anchored"))
            self._discharged_since_full = d.get("discharged_since_full")
