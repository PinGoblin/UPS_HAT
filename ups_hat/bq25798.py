"""Driver for the TI BQ25798 buck-boost charger (U2, I²C address 0x6B).

Register map: TI datasheet SLUSDV2. 16-bit registers are most significant byte first.
Voltages are in volts, currents in amps and temperatures in °C unless the name ends in
`_mv`, `_ma` or `_raw`.

The UPS HAT+ does not use OTG (it would drive VBUS on a sink-only USB-C port), the
ACFET/RBFET input switches or MPPT, so this driver deliberately offers no way to turn
them on. TS has no NTC on Rev D (fixed 60 % divider); `ts_ignore` is exposed for
completeness and is not used by [`UPS`][ups_hat.board.UPS].
"""

from .bus import I2CDevice, DeviceNotFound
from ._compat import const, clamp

ADDRESS = const(0x6B)

# Register addresses
REG_VSYSMIN = const(0x00)
REG_VREG = const(0x01)
REG_ICHG = const(0x03)
REG_VINDPM = const(0x05)
REG_IINDPM = const(0x06)
REG_PRECHG = const(0x08)
REG_TERM = const(0x09)
REG_RECHG = const(0x0A)
REG_IOTG = const(0x0D)
REG_TIMER = const(0x0E)
REG_CTRL0 = const(0x0F)
REG_CTRL1 = const(0x10)
REG_CTRL2 = const(0x11)
REG_CTRL3 = const(0x12)
REG_CTRL4 = const(0x13)
REG_CTRL5 = const(0x14)
REG_TEMP = const(0x16)
REG_NTC1 = const(0x18)
REG_ICO_ILIM = const(0x19)
REG_STAT0 = const(0x1B)
REG_STAT1 = const(0x1C)
REG_STAT2 = const(0x1D)
REG_STAT3 = const(0x1E)
REG_STAT4 = const(0x1F)
REG_FAULT0 = const(0x20)
REG_FAULT1 = const(0x21)
REG_FLAG0 = const(0x22)
REG_FAULT_FLAG0 = const(0x26)
REG_MASK0 = const(0x28)
REG_ADC_CTRL = const(0x2E)
REG_ADC_DIS0 = const(0x2F)
REG_ADC_DIS1 = const(0x30)
REG_IBUS_ADC = const(0x31)
REG_PART = const(0x48)

PART_NUMBER = const(3)  # REG48 PN[5:3] for BQ25798

# Code tables
CHG_STAT = ("not charging", "trickle charge", "pre-charge", "fast charge (CC)",
            "taper charge (CV)", "reserved", "top-off", "charge done")
"""Charge state names, indexed by the 3-bit charge state code."""
CHG_NOT_CHARGING = const(0)
CHG_TRICKLE = const(1)
CHG_PRECHARGE = const(2)
CHG_FAST = const(3)
CHG_TAPER = const(4)
CHG_TOPOFF = const(6)
CHG_DONE = const(7)

VBUS_STAT = {
    0x0: "no input",
    0x1: "USB SDP (500 mA)",
    0x2: "USB CDP (1.5 A)",
    0x3: "USB DCP (3.25 A)",
    0x4: "adjustable HVDCP (1.5 A)",
    0x5: "unknown adapter (3 A)",
    0x6: "non-standard adapter",
    0x7: "OTG",
    0x8: "not qualified adapter",
    0xB: "powered directly from VBUS",
    0xC: "backup mode",
}
ICO_STAT = ("disabled", "in progress", "maximum input current found", "reserved")
SDRV_IDLE = const(0)
"""`SDRV_CTRL` code: idle."""
SDRV_SHUTDOWN = const(1)
"""`SDRV_CTRL` code: shutdown mode (wakes only on adapter)."""
SDRV_SHIP = const(2)
"""`SDRV_CTRL` code: ship mode (wakes on SW1 or adapter)."""
SDRV_SYSTEM_RESET = const(3)
"""`SDRV_CTRL` code: system power reset."""
WATCHDOG_S = (0, 0.5, 1, 2, 20, 40, 80, 160)
CHG_TIMER_H = (5, 8, 12, 24)
TOPOFF_MIN = (0, 15, 30, 45)
VBAT_LOWV_PCT = (15.0, 62.2, 66.7, 71.4)
TRECHG_MS = (64, 256, 1024, 2048)
VAC_OVP_V = (26.0, 22.0, 12.0, 7.0)
VBUS_BACKUP_PCT = (40, 60, 80, 100)
TREG_C = (60, 80, 100, 120)
TSHUT_C = (150, 130, 120, 85)
IBAT_REG_A = (3.0, 4.0, 5.0, None)
ADC_BITS = (15, 14, 13, 12)

# Status / fault / flag bit names, (register, ((bit, name), ...))
STATUS_BITS = (
    (REG_STAT0, ((7, "IINDPM"), (6, "VINDPM"), (5, "WATCHDOG_EXPIRED"), (4, "POOR_SOURCE"),
                 (3, "POWER_GOOD"), (2, "AC2_PRESENT"), (1, "AC1_PRESENT"), (0, "VBUS_PRESENT"))),
    (REG_STAT1, ((0, "BC12_DONE"),)),
    (REG_STAT2, ((2, "THERMAL_REGULATION"), (1, "DPDM_DETECTING"), (0, "VBAT_PRESENT"))),
    (REG_STAT3, ((7, "ACRB2_PLACED"), (6, "ACRB1_PLACED"), (5, "ADC_DONE"), (4, "VSYSMIN_REGULATION"),
                 (3, "CHARGE_TIMER_EXPIRED"), (2, "TRICKLE_TIMER_EXPIRED"), (1, "PRECHARGE_TIMER_EXPIRED"))),
    (REG_STAT4, ((4, "VBAT_TOO_LOW_FOR_OTG"), (3, "TS_COLD"), (2, "TS_COOL"), (1, "TS_WARM"), (0, "TS_HOT"))),
)
FAULT_BITS = (
    (REG_FAULT0, ((7, "IBAT_REGULATION"), (6, "VBUS_OVP"), (5, "VBAT_OVP"), (4, "IBUS_OCP"),
                  (3, "IBAT_OCP"), (2, "CONVERTER_OCP"), (1, "VAC2_OVP"), (0, "VAC1_OVP"))),
    (REG_FAULT1, ((7, "VSYS_SHORT"), (6, "VSYS_OVP"), (5, "OTG_OVP"), (4, "OTG_UVP"), (2, "THERMAL_SHUTDOWN"))),
)
FLAG_BITS = (
    (0x22, ((7, "IINDPM"), (6, "VINDPM"), (5, "WATCHDOG_EXPIRED"), (4, "POOR_SOURCE"), (3, "POWER_GOOD"),
            (2, "AC2_PRESENT"), (1, "AC1_PRESENT"), (0, "VBUS_PRESENT"))),
    (0x23, ((7, "CHARGE_STATUS"), (6, "ICO"), (4, "VBUS_STATUS"), (2, "THERMAL_REGULATION"),
            (1, "VBAT_PRESENT"), (0, "BC12_DONE"))),
    (0x24, ((6, "DPDM_DONE"), (5, "ADC_DONE"), (4, "VSYSMIN_REGULATION"), (3, "CHARGE_TIMER_EXPIRED"),
            (2, "TRICKLE_TIMER_EXPIRED"), (1, "PRECHARGE_TIMER_EXPIRED"), (0, "TOPOFF_TIMER_EXPIRED"))),
    (0x25, ((4, "VBAT_TOO_LOW_FOR_OTG"), (3, "TS_COLD"), (2, "TS_COOL"), (1, "TS_WARM"), (0, "TS_HOT"))),
)
FAULT_FLAG_BITS = (
    (0x26, FAULT_BITS[0][1]),
    (0x27, FAULT_BITS[1][1]),
)


def _decode(regs, values):
    out = {}
    for i, (_, bits) in enumerate(regs):
        v = values[i]
        for b, name in bits:
            out[name] = bool((v >> b) & 1)
    return out


class ADCReading:
    """One set of ADC results, read in a single transfer.

    Args:
        raw: 22 bytes starting at register 0x31.

    Attributes:
        ibus (float): Input current (A).
        ibat (float): Battery current (A); positive = charging.
        vbus (float): Input voltage (V).
        vac1 (float): VAC1 voltage (V).
        vac2 (float): VAC2 voltage (V).
        vbat (float): Battery voltage (V).
        vsys (float): System rail voltage (V).
        ts_pct (float): TS input as % of REGN.
        tdie (float): Die temperature (°C).
        dplus (float): D+ voltage (V).
        dminus (float): D− voltage (V).
    """

    def __init__(self, raw):
        def s16(i):
            v = (raw[i] << 8) | raw[i + 1]
            return v - 0x10000 if v & 0x8000 else v

        def u16(i):
            return (raw[i] << 8) | raw[i + 1]

        self.ibus = s16(0) / 1000.0
        self.ibat = s16(2) / 1000.0
        self.vbus = u16(4) / 1000.0
        self.vac1 = u16(6) / 1000.0
        self.vac2 = u16(8) / 1000.0
        self.vbat = u16(10) / 1000.0
        self.vsys = u16(12) / 1000.0
        self.ts_pct = u16(14) * 0.0976563
        self.tdie = s16(16) * 0.5
        self.dplus = u16(18) / 1000.0
        self.dminus = u16(20) / 1000.0

    def to_dict(self):
        """Convert to a dictionary of the eleven readings."""
        return {k: getattr(self, k) for k in
                ("ibus", "ibat", "vbus", "vac1", "vac2", "vbat", "vsys", "ts_pct", "tdie", "dplus", "dminus")}

    def __repr__(self):
        return ("ADCReading(vbus={:.3f} V, ibus={:.3f} A, vbat={:.3f} V, ibat={:.3f} A, "
                "vsys={:.3f} V, tdie={:.1f} C)").format(self.vbus, self.ibus, self.vbat, self.ibat, self.vsys, self.tdie)


class BQ25798:
    """Register-level driver for the BQ25798.

    Every setting the board can safely use is a property; [`field()`][ups_hat.bq25798.BQ25798.field]
    and [`set_field()`][ups_hat.bq25798.BQ25798.set_field] give raw access to anything else.
    Setters clamp values to the chip's range and round to the nearest step.

    All methods and properties raise [`BusError`][ups_hat.bus.BusError] if a transfer fails.

    Args:
        i2c: Bus object with `readfrom_mem()` and `writeto_mem()`.
        address: 7-bit I²C address.
        check: Check the part number in register 0x48.

    Raises:
        DeviceNotFound: `check` is true and the part number is not the BQ25798's.
        BusError: The chip did not answer.
    """

    def __init__(self, i2c, address=ADDRESS, check=True):
        self.dev = I2CDevice(i2c, address, "BQ25798")
        if check:
            part = self.part_information()
            if part["part_number"] != PART_NUMBER:
                raise DeviceNotFound("BQ25798 not found at 0x%02X (REG48 = 0x%02X)" % (address, part["raw"]))

    # ---- raw access ------------------------------------------------------------------
    def field(self, reg, shift, width, wide=False):
        """Read a raw bit field.

        Args:
            reg: Register address (the high byte when `wide` is true).
            shift: Position of the field's lowest bit.
            width: Field width in bits.
            wide: The field is in a 16-bit register pair.

        Returns:
            The field value.
        """
        return self.dev.field(reg, shift, width, wide)

    def set_field(self, reg, shift, width, value, wide=False):
        """Write a raw bit field, leaving the other bits unchanged.

        Args:
            reg: Register address (the high byte when `wide` is true).
            shift: Position of the field's lowest bit.
            width: Field width in bits.
            value: New field value.
            wide: The field is in a 16-bit register pair.
        """
        self.dev.set_field(reg, shift, width, value, wide)

    def dump(self):
        """Read every register, 0x00 to 0x48.

        Returns:
            `{address: value}`.
        """
        data = self.dev.read(0x00, 0x49)
        return {i: data[i] for i in range(0x49)}

    def part_information(self):
        """Read the part information register (0x48).

        Returns:
            `{"raw": value, "part_number": pn, "revision": rev}`; the BQ25798 is part number 3.
        """
        v = self.dev.u8(REG_PART)
        return {"raw": v, "part_number": (v >> 3) & 7, "revision": v & 7}

    def reset_registers(self):
        """Return every register to its power-on default (`REG_RST`)."""
        self.dev.set_bit(REG_TERM, 6, True)

    # ---- voltage / current limits ----------------------------------------------------
    @property
    def min_system_voltage(self):
        """Minimum system voltage, VSYSMIN (V): 2.5–16 V in 250 mV steps."""
        return (self.dev.field(REG_VSYSMIN, 0, 6) * 250 + 2500) / 1000.0

    @min_system_voltage.setter
    def min_system_voltage(self, volts):
        code = int(round((clamp(volts, 2.5, 16.0) * 1000 - 2500) / 250))
        self.dev.set_field(REG_VSYSMIN, 0, 6, code)

    @property
    def charge_voltage(self):
        """Battery charge voltage, VREG (V): 3.0–18.8 V in 10 mV steps."""
        return self.dev.field(REG_VREG, 0, 11, True) * 10 / 1000.0

    @charge_voltage.setter
    def charge_voltage(self, volts):
        self.dev.set_field(REG_VREG, 0, 11, int(round(clamp(volts, 3.0, 18.8) * 100)), True)

    @property
    def charge_current(self):
        """Fast-charge current, ICHG (A): 0.05–5 A in 10 mA steps."""
        return self.dev.field(REG_ICHG, 0, 9, True) * 10 / 1000.0

    @charge_current.setter
    def charge_current(self, amps):
        self.dev.set_field(REG_ICHG, 0, 9, int(round(clamp(amps, 0.05, 5.0) * 100)), True)

    @property
    def input_voltage_limit(self):
        """Input voltage regulation limit, VINDPM (V): 3.6–22 V in 100 mV steps."""
        return self.dev.u8(REG_VINDPM) * 100 / 1000.0

    @input_voltage_limit.setter
    def input_voltage_limit(self, volts):
        self.dev.set_u8(REG_VINDPM, int(round(clamp(volts, 3.6, 22.0) * 10)))

    @property
    def input_current_limit(self):
        """Input current limit, IINDPM (A): 0.1–3.3 A in 10 mA steps."""
        return self.dev.field(REG_IINDPM, 0, 9, True) * 10 / 1000.0

    @input_current_limit.setter
    def input_current_limit(self, amps):
        self.dev.set_field(REG_IINDPM, 0, 9, int(round(clamp(amps, 0.1, 3.3) * 100)), True)

    @property
    def precharge_current(self):
        """Pre-charge current (A): 0.04–2 A in 40 mA steps."""
        return self.dev.field(REG_PRECHG, 0, 6) * 40 / 1000.0

    @precharge_current.setter
    def precharge_current(self, amps):
        self.dev.set_field(REG_PRECHG, 0, 6, int(round(clamp(amps, 0.04, 2.0) * 25)))

    @property
    def precharge_threshold_pct(self):
        """Pre-charge to fast-charge threshold, % of the charge voltage: 15, 62.2, 66.7 or 71.4."""
        return VBAT_LOWV_PCT[self.dev.field(REG_PRECHG, 6, 2)]

    @precharge_threshold_pct.setter
    def precharge_threshold_pct(self, pct):
        self.dev.set_field(REG_PRECHG, 6, 2, _nearest(VBAT_LOWV_PCT, pct))

    @property
    def termination_current(self):
        """Termination current (A): 0.04–1 A in 40 mA steps."""
        return self.dev.field(REG_TERM, 0, 5) * 40 / 1000.0

    @termination_current.setter
    def termination_current(self, amps):
        self.dev.set_field(REG_TERM, 0, 5, int(round(clamp(amps, 0.04, 1.0) * 25)))

    @property
    def stop_charge_on_watchdog(self):
        """Stop charging when the I²C watchdog expires."""
        return self.dev.bit(REG_TERM, 5)

    @stop_charge_on_watchdog.setter
    def stop_charge_on_watchdog(self, on):
        self.dev.set_bit(REG_TERM, 5, on)

    @property
    def cell_count(self):
        """Cells in series, set by the PROG resistor at power-up (2 on this board). Read only."""
        return self.dev.field(REG_RECHG, 6, 2) + 1

    @property
    def recharge_deglitch_ms(self):
        """Recharge deglitch time (ms): 64, 256, 1024 or 2048."""
        return TRECHG_MS[self.dev.field(REG_RECHG, 4, 2)]

    @recharge_deglitch_ms.setter
    def recharge_deglitch_ms(self, ms):
        self.dev.set_field(REG_RECHG, 4, 2, _nearest(TRECHG_MS, ms))

    @property
    def recharge_offset(self):
        """Recharge threshold below the charge voltage (V): 0.05–0.8 V in 50 mV steps."""
        return (self.dev.field(REG_RECHG, 0, 4) * 50 + 50) / 1000.0

    @recharge_offset.setter
    def recharge_offset(self, volts):
        self.dev.set_field(REG_RECHG, 0, 4, int(round((clamp(volts, 0.05, 0.8) * 1000 - 50) / 50)))

    @property
    def ico_current_limit(self):
        """Input current limit found by the ICO algorithm (A). Read only."""
        return self.dev.field(REG_ICO_ILIM, 0, 9, True) * 10 / 1000.0

    # ---- timers ----------------------------------------------------------------------
    @property
    def precharge_timer_short(self):
        """Pre-charge safety timer length: `True` = 0.5 h, `False` = 2 h."""
        return self.dev.bit(REG_IOTG, 7)

    @precharge_timer_short.setter
    def precharge_timer_short(self, on):
        self.dev.set_bit(REG_IOTG, 7, on)

    @property
    def topoff_timer_min(self):
        """Top-off timer after termination (minutes): 0, 15, 30 or 45."""
        return TOPOFF_MIN[self.dev.field(REG_TIMER, 6, 2)]

    @topoff_timer_min.setter
    def topoff_timer_min(self, minutes):
        self.dev.set_field(REG_TIMER, 6, 2, _nearest(TOPOFF_MIN, minutes))

    @property
    def trickle_timer_enabled(self):
        """Trickle-charge safety timer on."""
        return self.dev.bit(REG_TIMER, 5)

    @trickle_timer_enabled.setter
    def trickle_timer_enabled(self, on):
        self.dev.set_bit(REG_TIMER, 5, on)

    @property
    def precharge_timer_enabled(self):
        """Pre-charge safety timer on."""
        return self.dev.bit(REG_TIMER, 4)

    @precharge_timer_enabled.setter
    def precharge_timer_enabled(self, on):
        self.dev.set_bit(REG_TIMER, 4, on)

    @property
    def charge_timer_enabled(self):
        """Fast-charge safety timer on."""
        return self.dev.bit(REG_TIMER, 3)

    @charge_timer_enabled.setter
    def charge_timer_enabled(self, on):
        self.dev.set_bit(REG_TIMER, 3, on)

    @property
    def charge_timer_h(self):
        """Fast-charge safety timer length (hours): 5, 8, 12 or 24."""
        return CHG_TIMER_H[self.dev.field(REG_TIMER, 1, 2)]

    @charge_timer_h.setter
    def charge_timer_h(self, hours):
        self.dev.set_field(REG_TIMER, 1, 2, _nearest(CHG_TIMER_H, hours))

    @property
    def timer_half_rate(self):
        """Safety timers run at half speed during input limiting or thermal regulation."""
        return self.dev.bit(REG_TIMER, 0)

    @timer_half_rate.setter
    def timer_half_rate(self, on):
        self.dev.set_bit(REG_TIMER, 0, on)

    # ---- charger control 0 -----------------------------------------------------------
    @property
    def auto_battery_discharge_on_ovp(self):
        """Discharge the battery automatically on battery over-voltage."""
        return self.dev.bit(REG_CTRL0, 7)

    @auto_battery_discharge_on_ovp.setter
    def auto_battery_discharge_on_ovp(self, on):
        self.dev.set_bit(REG_CTRL0, 7, on)

    @property
    def force_battery_discharge(self):
        """Force a battery discharge current (about 30 mA)."""
        return self.dev.bit(REG_CTRL0, 6)

    @force_battery_discharge.setter
    def force_battery_discharge(self, on):
        self.dev.set_bit(REG_CTRL0, 6, on)

    @property
    def charge_enabled(self):
        """Charging allowed (`EN_CHG`)."""
        return self.dev.bit(REG_CTRL0, 5)

    @charge_enabled.setter
    def charge_enabled(self, on):
        self.dev.set_bit(REG_CTRL0, 5, on)

    @property
    def ico_enabled(self):
        """Input current optimiser (ICO) on."""
        return self.dev.bit(REG_CTRL0, 4)

    @ico_enabled.setter
    def ico_enabled(self, on):
        self.dev.set_bit(REG_CTRL0, 4, on)

    def force_ico(self):
        """Restart input current optimisation (needs `ico_enabled`)."""
        self.dev.set_bit(REG_CTRL0, 3, True)

    @property
    def hiz(self):
        """High-impedance input mode: the charger draws nothing from the adapter."""
        return self.dev.bit(REG_CTRL0, 2)

    @hiz.setter
    def hiz(self, on):
        self.dev.set_bit(REG_CTRL0, 2, on)

    @property
    def termination_enabled(self):
        """Charge termination on."""
        return self.dev.bit(REG_CTRL0, 1)

    @termination_enabled.setter
    def termination_enabled(self, on):
        self.dev.set_bit(REG_CTRL0, 1, on)

    # ---- charger control 1 -----------------------------------------------------------
    @property
    def vac_ovp(self):
        """VAC over-voltage threshold (V): 7, 12, 22 or 26."""
        return VAC_OVP_V[self.dev.field(REG_CTRL1, 4, 2)]

    @vac_ovp.setter
    def vac_ovp(self, volts):
        self.dev.set_field(REG_CTRL1, 4, 2, _nearest(VAC_OVP_V, volts))

    def kick_watchdog(self):
        """Reset the I²C watchdog timer."""
        self.dev.set_bit(REG_CTRL1, 3, True)

    @property
    def watchdog_s(self):
        """I²C watchdog period (s): 0 (off), 0.5, 1, 2, 20, 40, 80 or 160."""
        return WATCHDOG_S[self.dev.field(REG_CTRL1, 0, 3)]

    @watchdog_s.setter
    def watchdog_s(self, seconds):
        self.dev.set_field(REG_CTRL1, 0, 3, _nearest(WATCHDOG_S, seconds))

    # ---- charger control 2: input detection and ship FET -----------------------------
    def force_input_detection(self):
        """Re-run D+/D− adapter detection."""
        self.dev.set_bit(REG_CTRL2, 7, True)

    @property
    def auto_input_detection(self):
        """Run D+/D− adapter detection automatically when VBUS appears."""
        return self.dev.bit(REG_CTRL2, 6)

    @auto_input_detection.setter
    def auto_input_detection(self, on):
        self.dev.set_bit(REG_CTRL2, 6, on)

    @property
    def hvdcp(self):
        """HVDCP settings as `(HVDCP_EN, EN_9V, EN_12V)`. Read only.

        The UPS HAT+ negotiates voltage with the STUSB4500, so leave these off.
        """
        v = self.dev.u8(REG_CTRL2)
        return (bool(v & 0x08), bool(v & 0x10), bool(v & 0x20))

    @property
    def ship_fet_control(self):
        """`SDRV_CTRL` field: one of the `SDRV_*` codes. Read only; write with
        [`set_ship_fet_control()`][ups_hat.bq25798.BQ25798.set_ship_fet_control].
        """
        return self.dev.field(REG_CTRL2, 1, 2)

    def set_ship_fet_control(self, mode, delay=False):
        """Write the ship FET control field (`SDRV_CTRL`).

        Needs [`sfet_present`][ups_hat.bq25798.BQ25798.sfet_present] set, otherwise the chip
        ignores it.

        Args:
            mode: `SDRV_IDLE`, `SDRV_SHUTDOWN`, `SDRV_SHIP` or `SDRV_SYSTEM_RESET`.
            delay: Add TI's 10 s delay before acting.
        """
        v = self.dev.u8(REG_CTRL2)
        v = (v & ~0x07) | ((mode & 3) << 1) | (0 if delay else 1)
        self.dev.set_u8(REG_CTRL2, v)

    # ---- charger control 3 / 4 -------------------------------------------------------
    @property
    def pfm_forward_disabled(self):
        """PFM (light-load pulse-frequency mode) off in forward mode."""
        return self.dev.bit(REG_CTRL3, 4)

    @pfm_forward_disabled.setter
    def pfm_forward_disabled(self, on):
        self.dev.set_bit(REG_CTRL3, 4, on)

    @property
    def ship_wakeup_short(self):
        """QON press that wakes from ship mode: `True` = 15 ms, `False` = 1 s."""
        return self.dev.bit(REG_CTRL3, 3)

    @ship_wakeup_short.setter
    def ship_wakeup_short(self, on):
        self.dev.set_bit(REG_CTRL3, 3, on)

    @property
    def batfet_ldo_disabled(self):
        """BATFET LDO mode off during pre-charge."""
        return self.dev.bit(REG_CTRL3, 2)

    @batfet_ldo_disabled.setter
    def batfet_ldo_disabled(self, on):
        self.dev.set_bit(REG_CTRL3, 2, on)

    @property
    def forward_ooa_disabled(self):
        """Out-of-audio mode off in forward mode."""
        return self.dev.bit(REG_CTRL3, 0)

    @forward_ooa_disabled.setter
    def forward_ooa_disabled(self, on):
        self.dev.set_bit(REG_CTRL3, 0, on)

    @property
    def switching_frequency_khz(self):
        """Converter switching frequency (kHz), set by the PROG resistor at power-up (750 on this board). Read only."""
        return 750 if self.dev.bit(REG_CTRL4, 5) else 1500

    @property
    def stat_pin_disabled(self):
        """STAT pin output off."""
        return self.dev.bit(REG_CTRL4, 4)

    @stat_pin_disabled.setter
    def stat_pin_disabled(self, on):
        self.dev.set_bit(REG_CTRL4, 4, on)

    @property
    def vsys_short_protection(self):
        """VSYS short-circuit protection (hiccup mode) on."""
        return not self.dev.bit(REG_CTRL4, 3)

    @vsys_short_protection.setter
    def vsys_short_protection(self, on):
        self.dev.set_bit(REG_CTRL4, 3, not on)

    def force_vindpm_detection(self):
        """Re-measure the adapter's open-circuit voltage to set VINDPM."""
        self.dev.set_bit(REG_CTRL4, 1, True)

    @property
    def ibus_ocp_enabled(self):
        """Input over-current protection on."""
        return self.dev.bit(REG_CTRL4, 0)

    @ibus_ocp_enabled.setter
    def ibus_ocp_enabled(self, on):
        self.dev.set_bit(REG_CTRL4, 0, on)

    # ---- charger control 5 -----------------------------------------------------------
    @property
    def sfet_present(self):
        """A ship FET is fitted (`SFET_PRESENT`).

        Must be `True` for `SDRV_CTRL` (ship, shutdown, reset) and QON to work. Returns to
        `False` whenever the chip loses all power.
        """
        return self.dev.bit(REG_CTRL5, 7)

    @sfet_present.setter
    def sfet_present(self, on):
        self.dev.set_bit(REG_CTRL5, 7, on)

    @property
    def ibat_discharge_sensing(self):
        """Measure discharge current in battery-only mode (`EN_IBAT`). Needed for IBAT on battery."""
        return self.dev.bit(REG_CTRL5, 5)

    @ibat_discharge_sensing.setter
    def ibat_discharge_sensing(self, on):
        self.dev.set_bit(REG_CTRL5, 5, on)

    @property
    def iindpm_enabled(self):
        """Input current regulation (IINDPM) on."""
        return self.dev.bit(REG_CTRL5, 2)

    @iindpm_enabled.setter
    def iindpm_enabled(self, on):
        self.dev.set_bit(REG_CTRL5, 2, on)

    @property
    def ilim_pin_enabled(self):
        """ILIM_HIZ pin current limit on."""
        return self.dev.bit(REG_CTRL5, 1)

    @ilim_pin_enabled.setter
    def ilim_pin_enabled(self, on):
        self.dev.set_bit(REG_CTRL5, 1, on)

    @property
    def battery_ocp_enabled(self):
        """Turn the ship FET off on battery discharge over-current (`EN_BATOC`, needs `sfet_present`)."""
        return self.dev.bit(REG_CTRL5, 0)

    @battery_ocp_enabled.setter
    def battery_ocp_enabled(self, on):
        self.dev.set_bit(REG_CTRL5, 0, on)

    # ---- temperature control ---------------------------------------------------------
    @property
    def thermal_regulation_c(self):
        """Die temperature at which charge current is reduced (°C): 60, 80, 100 or 120."""
        return TREG_C[self.dev.field(REG_TEMP, 6, 2)]

    @thermal_regulation_c.setter
    def thermal_regulation_c(self, deg):
        self.dev.set_field(REG_TEMP, 6, 2, _nearest(TREG_C, deg))

    @property
    def thermal_shutdown_c(self):
        """Die temperature at which the charger shuts down (°C): 85, 120, 130 or 150."""
        return TSHUT_C[self.dev.field(REG_TEMP, 4, 2)]

    @thermal_shutdown_c.setter
    def thermal_shutdown_c(self, deg):
        self.dev.set_field(REG_TEMP, 4, 2, _nearest(TSHUT_C, deg))

    @property
    def vbus_pulldown(self):
        """VBUS pull-down resistor on."""
        return self.dev.bit(REG_TEMP, 3)

    @vbus_pulldown.setter
    def vbus_pulldown(self, on):
        self.dev.set_bit(REG_TEMP, 3, on)

    @property
    def ts_ignore(self):
        """Ignore the TS pin (`TS_IGNORE`, register 0x18 bit 0).

        `True` makes the charger behave as if at room temperature: no JEITA limits and no
        cold/hot stop. Reset to `False` by power-on reset, `REG_RST` and the I²C watchdog, so
        re-apply it after any charger reset. Not used on Rev D, whose TS divider already reads
        as normal temperature.
        """
        return self.dev.bit(REG_NTC1, 0)

    @ts_ignore.setter
    def ts_ignore(self, on):
        self.dev.set_bit(REG_NTC1, 0, on)

    # ---- status ----------------------------------------------------------------------
    def status(self):
        """Read the live status registers (0x1B to 0x1F).

        Returns:
            A dict of booleans named after the status bits (for example `POWER_GOOD`,
            `VBUS_PRESENT`, `VBAT_PRESENT`, `TS_COLD`), plus `charge_state` and
            `charge_state_text`, `vbus_type` and `vbus_type_text`, and `ico_state` and
            `ico_state_text`.
        """
        raw = self.dev.read(REG_STAT0, 5)
        out = _decode(STATUS_BITS, raw)
        cs = (raw[1] >> 5) & 7
        out["charge_state"] = cs
        out["charge_state_text"] = CHG_STAT[cs]
        vb = (raw[1] >> 1) & 0xF
        out["vbus_type"] = vb
        out["vbus_type_text"] = VBUS_STAT.get(vb, "reserved (0x%X)" % vb)
        ico = (raw[2] >> 6) & 3
        out["ico_state"] = ico
        out["ico_state_text"] = ICO_STAT[ico]
        return out

    def faults(self):
        """Read the fault conditions active now (registers 0x20 and 0x21).

        Returns:
            Fault names, for example `["VBAT_OVP"]`.
        """
        raw = self.dev.read(REG_FAULT0, 2)
        d = _decode(FAULT_BITS, raw)
        return [k for k in d if d[k]]

    def read_flags(self):
        """Read and clear the latched event flags (registers 0x22 to 0x27).

        Call on every poll so short events between polls are not missed: INT is not connected
        on this board.

        Returns:
            `{"charger": [names], "fault": [names]}`.
        """
        raw = self.dev.read(REG_FLAG0, 6)
        ch = _decode(FLAG_BITS, raw[0:4])
        ft = _decode(FAULT_FLAG_BITS, raw[4:6])
        return {"charger": [k for k in ch if ch[k]], "fault": [k for k in ft if ft[k]]}

    # ---- ADC -------------------------------------------------------------------------
    def adc_enable(self, on=True, continuous=True, bits=15, average=False):
        """Configure and start the ADC.

        Args:
            on: ADC on.
            continuous: Convert continuously; `False` takes one reading.
            bits: Resolution: 12, 13, 14 or 15 (nearest is used).
            average: Running average on.
        """
        code = _nearest(ADC_BITS, bits)
        v = (0x80 if on else 0) | (0 if continuous else 0x40) | (code << 4) | (0x08 if average else 0) \
            | (0x04 if average else 0)
        self.dev.set_u8(REG_ADC_CTRL, v)

    @property
    def adc_enabled(self):
        """ADC on."""
        return self.dev.bit(REG_ADC_CTRL, 7)

    @property
    def adc_disable_mask(self):
        """Raw channel-disable bits as `(REG0x2F, REG0x30)`; `(0, 0)` = all channels on."""
        return (self.dev.u8(REG_ADC_DIS0), self.dev.u8(REG_ADC_DIS1))

    def read_adc(self):
        """Read every ADC channel in one transfer.

        Returns:
            The readings.
        """
        return ADCReading(self.dev.read(REG_IBUS_ADC, 22))


def _nearest(table, value):
    best, err = 0, None
    for i, t in enumerate(table):
        if t is None:
            continue
        e = abs(t - value)
        if err is None or e < err:
            best, err = i, e
    return best
