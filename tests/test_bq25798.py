"""ups_hat.bq25798: register-level charger driver, against the register simulator."""

import unittest

import helpers
from sim import FakeI2C
from ups_hat import bq25798 as bq
from ups_hat.bq25798 import BQ25798, ADCReading
from ups_hat.bus import BusError, DeviceNotFound


def adc_bytes(**mv):
    names = ("ibus", "ibat", "vbus", "vac1", "vac2", "vbat", "vsys", "ts", "tdie", "dp", "dm")
    out = bytearray()
    for n in names:
        v = int(mv.get(n, 0)) & 0xFFFF
        out += bytes((v >> 8, v & 0xFF))
    return bytes(out)


class ConstructionTests(unittest.TestCase):
    def test_finds_part(self):
        c = BQ25798(FakeI2C(pd=False))
        self.assertEqual(c.part_information(), {"raw": 0x19, "part_number": 3, "revision": 1})

    def test_wrong_part_number(self):
        bus = FakeI2C(pd=False)
        bus.bq.r[0x48] = 0x21                   # PN 4: not a BQ25798
        with self.assertRaises(DeviceNotFound):
            BQ25798(bus)
        BQ25798(bus, check=False)               # allowed when asked

    def test_missing_chip(self):
        with self.assertRaises(BusError):
            BQ25798(FakeI2C(bq=False, pd=False))


class SettingTests(unittest.TestCase):
    """Every numeric setting: round trip, step rounding and clamping to the chip's range."""

    CASES = [
        # (property, value written, value read back)
        ("min_system_voltage", 7.0, 7.0), ("min_system_voltage", 6.6, 6.5), ("min_system_voltage", 1.0, 2.5),
        ("min_system_voltage", 20.0, 16.0),
        ("charge_voltage", 8.2, 8.2), ("charge_voltage", 8.204, 8.2), ("charge_voltage", 2.0, 3.0),
        ("charge_voltage", 25.0, 18.8),
        ("charge_current", 1.5, 1.5), ("charge_current", 0.0, 0.05), ("charge_current", 9.0, 5.0),
        ("input_voltage_limit", 8.0, 8.0), ("input_voltage_limit", 1.0, 3.6), ("input_voltage_limit", 30.0, 22.0),
        ("input_current_limit", 3.0, 3.0), ("input_current_limit", 0.0, 0.1), ("input_current_limit", 5.0, 3.3),
        ("precharge_current", 0.2, 0.2), ("precharge_current", 0.0, 0.04), ("precharge_current", 5.0, 2.0),
        ("termination_current", 0.12, 0.12), ("termination_current", 0.0, 0.04), ("termination_current", 3.0, 1.0),
        ("recharge_offset", 0.1, 0.1), ("recharge_offset", 0.0, 0.05), ("recharge_offset", 2.0, 0.8),
        ("precharge_threshold_pct", 70, 71.4), ("precharge_threshold_pct", 10, 15.0),
        ("recharge_deglitch_ms", 1000, 1024), ("topoff_timer_min", 20, 15), ("charge_timer_h", 10, 8),
        ("charge_timer_h", 100, 24), ("vac_ovp", 13, 12.0), ("watchdog_s", 0, 0), ("watchdog_s", 35, 40),
        ("thermal_regulation_c", 95, 100), ("thermal_shutdown_c", 123, 120), ("thermal_shutdown_c", 90, 85),
    ]

    BOOLS = ["stop_charge_on_watchdog", "precharge_timer_short", "trickle_timer_enabled",
             "precharge_timer_enabled", "charge_timer_enabled", "timer_half_rate",
             "auto_battery_discharge_on_ovp", "force_battery_discharge", "charge_enabled", "ico_enabled", "hiz",
             "termination_enabled", "auto_input_detection", "pfm_forward_disabled", "ship_wakeup_short",
             "batfet_ldo_disabled", "forward_ooa_disabled", "stat_pin_disabled", "vsys_short_protection",
             "ibus_ocp_enabled", "sfet_present", "ibat_discharge_sensing", "iindpm_enabled", "ilim_pin_enabled",
             "battery_ocp_enabled", "vbus_pulldown", "ts_ignore"]

    def setUp(self):
        self.bus = FakeI2C(pd=False)
        self.c = BQ25798(self.bus)

    def test_numeric_settings(self):
        for name, value, expected in self.CASES:
            with self.subTest(name=name, value=value):
                setattr(self.c, name, value)
                self.assertAlmostEqual(getattr(self.c, name), expected, places=6)

    def test_boolean_settings_round_trip_and_leave_neighbours(self):
        for name in self.BOOLS:
            with self.subTest(name=name):
                before = bytes(self.bus.bq.r)
                original = getattr(self.c, name)
                setattr(self.c, name, not original)
                self.assertEqual(getattr(self.c, name), not original)
                changed = [i for i in range(0x49) if self.bus.bq.r[i] != before[i]]
                self.assertEqual(len(changed), 1, "exactly one register changes")
                self.assertEqual(bin(self.bus.bq.r[changed[0]] ^ before[changed[0]]).count("1"), 1,
                                 "exactly one bit changes")
                setattr(self.c, name, original)
                self.assertEqual(bytes(self.bus.bq.r), before)

    def test_vsys_short_protection_is_inverted_bit(self):
        self.c.vsys_short_protection = False
        self.assertTrue(self.bus.bq.r[0x13] & 0x08)
        self.c.vsys_short_protection = True
        self.assertFalse(self.bus.bq.r[0x13] & 0x08)

    def test_read_only_values(self):
        self.assertEqual(self.c.cell_count, 2)
        self.assertEqual(self.c.switching_frequency_khz, 750)
        self.bus.bq.r[0x13] &= ~0x20
        self.assertEqual(self.c.switching_frequency_khz, 1500)
        self.bus.bq.r[0x19], self.bus.bq.r[0x1A] = 0x00, 0xC8
        self.assertAlmostEqual(self.c.ico_current_limit, 2.0)

    def test_hvdcp_tuple(self):
        self.bus.bq.r[0x11] = 0x18
        self.assertEqual(self.c.hvdcp, (True, True, False))

    def test_raw_field_access(self):
        self.c.set_field(0x0A, 6, 2, 0b11)               # CELL field: 4S
        self.assertEqual(self.c.field(0x0A, 6, 2), 3)
        self.assertEqual(self.c.cell_count, 4)
        self.c.set_field(0x01, 0, 11, 820, wide=True)
        self.assertEqual(self.c.field(0x01, 0, 11, wide=True), 820)

    def test_dump(self):
        d = self.c.dump()
        self.assertEqual(len(d), 0x49)
        self.assertEqual(d[0x48], 0x19)


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.bus = FakeI2C(pd=False)
        self.c = BQ25798(self.bus)

    def test_reset_registers_restores_defaults(self):
        self.c.charge_voltage = 8.2
        self.c.reset_registers()
        self.assertAlmostEqual(self.c.charge_voltage, 8.4)

    def test_kick_watchdog_sets_self_clearing_bit(self):
        self.c.kick_watchdog()
        self.assertIn((0x10, bytes([0x8D])), self.bus.bq.writes)

    def test_strobes_write_their_bit(self):
        for method, reg, bit in (("force_ico", 0x0F, 3), ("force_input_detection", 0x11, 7),
                                 ("force_vindpm_detection", 0x13, 1)):
            with self.subTest(method=method):
                getattr(self.c, method)()
                reg_w, data = self.bus.bq.writes[-1]
                self.assertEqual(reg_w, reg)
                self.assertTrue(data[0] >> bit & 1)

    def test_ship_fet_control_needs_sfet_present(self):
        self.c.set_ship_fet_control(bq.SDRV_SHIP)
        self.assertEqual(self.c.ship_fet_control, bq.SDRV_IDLE, "locked until SFET_PRESENT")
        self.c.sfet_present = True
        for mode in (bq.SDRV_SHUTDOWN, bq.SDRV_SHIP, bq.SDRV_SYSTEM_RESET, bq.SDRV_IDLE):
            with self.subTest(mode=mode):
                self.c.set_ship_fet_control(mode)
                self.assertEqual(self.c.ship_fet_control, mode)
                self.assertEqual(self.bus.bq.r[0x11] & 1, 1, "no delay")
        self.c.set_ship_fet_control(bq.SDRV_SHIP, delay=True)
        self.assertEqual(self.bus.bq.r[0x11] & 1, 0)

    def test_adc_enable_encodings(self):
        self.c.adc_enable(True, continuous=True, bits=15)
        self.assertEqual(self.bus.bq.r[0x2E], 0x80)
        self.assertTrue(self.c.adc_enabled)
        self.c.adc_enable(True, continuous=False, bits=12, average=True)
        self.assertEqual(self.bus.bq.r[0x2E], 0x80 | 0x40 | (3 << 4) | 0x0C)
        self.c.adc_enable(False)
        self.assertFalse(self.c.adc_enabled)
        self.assertEqual(self.c.adc_disable_mask, (0, 0))


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.bus = FakeI2C(pd=False)
        self.c = BQ25798(self.bus)

    def test_status_decoding(self):
        self.bus.bq.set_status(vbus=True, pg=True, chg=4, s3=0x08)
        self.bus.bq.r[0x1D] |= 0x80                        # ICO: maximum found
        self.bus.bq.r[0x1F] = 0x0A                         # TS_COLD, TS_WARM
        st = self.c.status()
        self.assertTrue(st["VBUS_PRESENT"] and st["POWER_GOOD"] and st["VBAT_PRESENT"])
        self.assertEqual((st["charge_state"], st["charge_state_text"]), (4, "taper charge (CV)"))
        self.assertEqual((st["vbus_type"], st["vbus_type_text"]), (5, "unknown adapter (3 A)"))
        self.assertEqual(st["ico_state_text"], "maximum input current found")
        self.assertTrue(st["CHARGE_TIMER_EXPIRED"])
        self.assertTrue(st["TS_COLD"] and st["TS_WARM"] and not st["TS_HOT"])

    def test_reserved_vbus_type(self):
        self.bus.bq.r[0x1C] = 0x0A << 1
        self.assertEqual(self.c.status()["vbus_type_text"], "reserved (0xA)")

    def test_every_charge_state_named(self):
        for code in range(8):
            with self.subTest(code=code):
                self.bus.bq.set_status(chg=code)
                self.assertEqual(self.c.status()["charge_state_text"], bq.CHG_STAT[code])

    def test_faults(self):
        self.assertEqual(self.c.faults(), [])
        self.bus.bq.set_status(fault0=0x20 | 0x01, fault1=0x04)
        self.assertEqual(sorted(self.c.faults()), ["THERMAL_SHUTDOWN", "VAC1_OVP", "VBAT_OVP"])

    def test_flags_clear_on_read(self):
        self.bus.bq.flags[0] = 0x10                         # POOR_SOURCE
        self.bus.bq.flags[4] = 0x40                         # VBUS_OVP came and went
        self.assertEqual(self.c.read_flags(), {"charger": ["POOR_SOURCE"], "fault": ["VBUS_OVP"]})
        self.assertEqual(self.c.read_flags(), {"charger": [], "fault": []})

    def test_bit_tables_have_unique_bits(self):
        for table in (bq.STATUS_BITS, bq.FAULT_BITS, bq.FLAG_BITS):
            for reg, bits in table:
                with self.subTest(reg=hex(reg)):
                    nums = [b for b, _ in bits]
                    self.assertEqual(len(nums), len(set(nums)))
                    self.assertTrue(all(0 <= b <= 7 for b in nums))


class ADCTests(unittest.TestCase):
    def test_decode(self):
        a = ADCReading(adc_bytes(ibus=1200, ibat=-1500, vbus=9000, vbat=7800, vsys=7900,
                                 ts=614, tdie=-10, dp=600, dm=550, vac1=9010, vac2=0))
        self.assertAlmostEqual(a.ibus, 1.2)
        self.assertAlmostEqual(a.ibat, -1.5)
        self.assertAlmostEqual(a.vbus, 9.0)
        self.assertAlmostEqual(a.vbat, 7.8)
        self.assertAlmostEqual(a.vsys, 7.9)
        self.assertAlmostEqual(a.tdie, -5.0)
        self.assertAlmostEqual(a.ts_pct, 614 * 0.0976563)
        self.assertAlmostEqual(a.dplus, 0.6)
        self.assertAlmostEqual(a.dminus, 0.55)
        self.assertAlmostEqual(a.vac1, 9.01)

    def test_voltages_are_unsigned(self):
        a = ADCReading(adc_bytes(vbus=0xFFFF))
        self.assertAlmostEqual(a.vbus, 65.535)

    def test_to_dict_and_repr(self):
        a = ADCReading(adc_bytes(vbus=5000))
        d = a.to_dict()
        self.assertEqual(set(d), {"ibus", "ibat", "vbus", "vac1", "vac2", "vbat", "vsys", "ts_pct", "tdie",
                                  "dplus", "dminus"})
        self.assertIn("vbus=5.000 V", repr(a))

    def test_read_adc_from_chip(self):
        bus = FakeI2C(pd=False)
        helpers.set_adc(bus, vbat=7400, ibat=-800)
        a = BQ25798(bus).read_adc()
        self.assertAlmostEqual(a.vbat, 7.4)
        self.assertAlmostEqual(a.ibat, -0.8)


class NearestTests(unittest.TestCase):
    def test_nearest(self):
        self.assertEqual(bq._nearest((5, 8, 12, 24), 10), 1)   # tie goes to the first
        self.assertEqual(bq._nearest((5, 8, 12, 24), 11), 2)
        self.assertEqual(bq._nearest(bq.IBAT_REG_A, 100.0), 2, "None entries are skipped")
        self.assertEqual(bq._nearest(bq.WATCHDOG_S, -5), 0)


if __name__ == "__main__":
    unittest.main()
