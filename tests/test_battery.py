"""ups_hat.battery: OCV table and the BatteryMonitor state-of-charge model."""

import json
import unittest

import helpers  # noqa: F401
from ups_hat.battery import OCV_TABLE, BatteryMonitor, soc_from_ocv


class OcvTests(unittest.TestCase):
    def test_table_shape(self):
        self.assertEqual(len(OCV_TABLE), 21)
        self.assertEqual(list(OCV_TABLE), sorted(OCV_TABLE), "OCV table must be increasing")
        self.assertEqual(len(set(OCV_TABLE)), len(OCV_TABLE), "no flat steps (division by zero)")

    def test_limits(self):
        self.assertEqual(soc_from_ocv(2.5), 0.0)
        self.assertEqual(soc_from_ocv(OCV_TABLE[0]), 0.0)
        self.assertEqual(soc_from_ocv(4.20), 100.0)
        self.assertEqual(soc_from_ocv(4.5), 100.0)

    def test_table_points(self):
        for i, v in enumerate(OCV_TABLE[1:-1], start=1):
            with self.subTest(v=v):
                self.assertAlmostEqual(soc_from_ocv(v), i * 5.0, places=6)

    def test_interpolates_between_points(self):
        mid = (OCV_TABLE[10] + OCV_TABLE[11]) / 2
        self.assertAlmostEqual(soc_from_ocv(mid), 52.5, places=6)

    def test_monotonic(self):
        prev = -1.0
        v = 3.0
        while v <= 4.3:
            s = soc_from_ocv(v)
            self.assertGreaterEqual(s, prev)
            prev = s
            v += 0.001


class MonitorBasicsTests(unittest.TestCase):
    def test_defaults(self):
        b = BatteryMonitor()
        self.assertIsNone(b.soc)
        self.assertIsNone(b.remaining_mah)
        self.assertFalse(b.anchored)
        self.assertEqual(b.cycles, 0.0)

    def test_nominal_capacity_scales_with_full_voltage_and_parallel(self):
        b = BatteryMonitor(parallel=1, cell_capacity_mah=3000, full_cell_voltage=4.20)
        self.assertAlmostEqual(b.nominal_capacity_mah, 3000.0)
        b41 = BatteryMonitor(parallel=1, cell_capacity_mah=3000, full_cell_voltage=4.10)
        self.assertAlmostEqual(b41.nominal_capacity_mah, 3000 * soc_from_ocv(4.10) / 100)
        b2 = BatteryMonitor(parallel=2, cell_capacity_mah=3000, full_cell_voltage=4.10)
        self.assertAlmostEqual(b2.nominal_capacity_mah, 2 * b41.nominal_capacity_mah)

    def test_capacity_prefers_learned(self):
        b = BatteryMonitor()
        b.learned_capacity_mah = 1234.0
        self.assertEqual(b.capacity_mah, 1234.0)

    def test_soc_from_voltage_relative_to_full_point(self):
        b = BatteryMonitor(full_cell_voltage=4.10)
        self.assertAlmostEqual(b.soc_from_voltage(8.20), 100.0)
        self.assertAlmostEqual(b.soc_from_voltage(8.40), 100.0)  # clamped
        self.assertEqual(b.soc_from_voltage(6.0), 0.0)

    def test_first_update_estimates_from_voltage(self):
        b = BatteryMonitor(full_cell_voltage=4.20)
        b.update(0.0, 7.60, -1.0)
        self.assertAlmostEqual(b.soc, soc_from_ocv(3.80))
        self.assertAlmostEqual(b.remaining_mah, b.capacity_mah * b.soc / 100)

    def test_not_present_skips_and_breaks_integration(self):
        b = BatteryMonitor()
        b.update(0.0, 7.6, -1.0)
        b.update(1.0, 7.6, -1.0, present=False)
        rem = b.remaining_mah
        b.update(3601.0, 7.6, -1.0)          # no integration across the gap
        self.assertEqual(b.remaining_mah, rem)


class CoulombCountingTests(unittest.TestCase):
    def make(self):
        b = BatteryMonitor(parallel=1, cell_capacity_mah=3000, full_cell_voltage=4.20)
        b.update(0.0, 8.4, 0.0, charge_done=True)  # anchored at 100 %
        return b

    def test_charge_done_anchors_full(self):
        b = self.make()
        self.assertEqual(b.soc, 100.0)
        self.assertTrue(b.anchored)
        self.assertEqual(b.remaining_mah, b.capacity_mah)

    def test_one_hour_at_one_amp(self):
        b = self.make()
        for t in range(10, 3601, 10):
            b.update(float(t), 7.8, -1.0)
        # trapezoid: first step averages 0 A and -1 A
        self.assertAlmostEqual(b.remaining_mah, 3000 - 1000 + 1000 * 5 / 3600, places=3)
        self.assertAlmostEqual(b.cycle_mah, 1000 - 1000 * 5 / 3600, places=3)
        self.assertAlmostEqual(b.soc, b.remaining_mah / 3000 * 100)

    def test_clamped_to_capacity_and_zero(self):
        b = self.make()
        b.update(10.0, 8.4, 5.0)
        b.update(20.0, 8.4, 5.0)
        self.assertEqual(b.remaining_mah, b.capacity_mah)
        for t in range(30, 30000, 100):
            b.update(float(t), 6.0, -5.0)
        self.assertEqual(b.remaining_mah, 0.0)
        self.assertEqual(b.soc, 0.0)

    def test_gaps_of_ten_minutes_or_more_are_ignored(self):
        b = self.make()
        b.update(600.0, 7.8, -1.0)
        self.assertEqual(b.remaining_mah, b.capacity_mah)

    def test_time_estimates(self):
        b = self.make()
        b.update(10.0, 7.8, -2.0)
        rem = b.remaining_mah
        self.assertAlmostEqual(b.time_to_empty_h(-2.0), rem / 2000.0)
        self.assertIsNone(b.time_to_empty_h(-0.01))
        self.assertIsNone(b.time_to_empty_h(0.5))
        self.assertAlmostEqual(b.time_to_full_h(1.0), (b.capacity_mah - rem) / 1000.0 * 1.15)
        self.assertIsNone(b.time_to_full_h(0.01))
        self.assertIsNone(BatteryMonitor().time_to_full_h(1.0))
        self.assertIsNone(BatteryMonitor().time_to_empty_h(-1.0))

    def test_cycles(self):
        b = self.make()
        b.cycle_mah = b.capacity_mah * 2.5
        self.assertAlmostEqual(b.cycles, 2.5)


class RestCorrectionTests(unittest.TestCase):
    def test_rest_corrects_large_error_once_per_period(self):
        b = BatteryMonitor(full_cell_voltage=4.20)
        b.update(0.0, 8.4, 0.0, charge_done=True)
        b.charge_done = None
        # pretend the counter drifted: pack is really at 3.80 V/cell after a long rest
        t = 10.0
        b.update(t, 7.60, 0.0)
        while t < 10 + BatteryMonitor.REST_TIME + 5:
            t += 60
            b.update(t, 7.60, 0.0)
        self.assertAlmostEqual(b.soc, soc_from_ocv(3.80), places=3)

    def test_small_error_kept_when_anchored(self):
        b = BatteryMonitor(full_cell_voltage=4.20)
        b.update(0.0, 8.4, 0.0, charge_done=True)
        b.soc = soc_from_ocv(4.10) + 5   # within 10 % of the rested estimate
        b.remaining_mah = b.capacity_mah * b.soc / 100
        t = 0.0
        while t < BatteryMonitor.REST_TIME + 100:
            t += 60
            b.update(t, 8.20, 0.0)
        self.assertAlmostEqual(b.soc, soc_from_ocv(4.10) + 5, places=6)

    def test_load_restarts_the_rest_timer(self):
        b = BatteryMonitor()
        b.update(0.0, 7.6, 0.0)
        b.update(1000.0, 7.6, 0.0)
        b.update(1100.0, 7.6, -1.0)
        self.assertIsNone(b._rest_since)

    def test_capacity_learned_after_deep_discharge(self):
        b = BatteryMonitor(parallel=1, cell_capacity_mah=3000, full_cell_voltage=4.20)
        b.update(0.0, 8.4, 0.0, charge_done=True)
        b._discharged_since_full = 2000.0        # mAh taken out since full
        b._ocv_correct(2 * 3.75)                 # rested at 25 %: 2000 / 0.75 = 2667 mAh
        self.assertAlmostEqual(b.learned_capacity_mah, 2000 / (1 - soc_from_ocv(3.75) / 100), places=3)
        self.assertIsNone(b._discharged_since_full)
        first = b.learned_capacity_mah
        b._discharged_since_full = 1500.0
        b._ocv_correct(2 * 3.75)                 # smoothed 70/30
        self.assertAlmostEqual(b.learned_capacity_mah, 0.7 * first + 0.3 * (1500 / 0.75), places=3)

    def test_implausible_capacity_is_ignored(self):
        b = BatteryMonitor(parallel=1, cell_capacity_mah=3000, full_cell_voltage=4.20)
        b._discharged_since_full = 2900.0
        b.soc = 50.0
        b._ocv_correct(2 * 4.0)                  # would imply far more than 1.5 x rated
        self.assertIsNone(b.learned_capacity_mah)


class ResistanceTests(unittest.TestCase):
    def test_load_steps_give_resistance_and_baseline(self):
        b = BatteryMonitor()
        R = 0.15
        t = 0.0
        for k in range(42):
            i = -2.0 if k % 2 else -0.2
            t += 2.0
            b.update(t, 7.6 + R * i, i)
        self.assertAlmostEqual(b.resistance, R, places=4)
        self.assertAlmostEqual(b.resistance_baseline, R, places=4)

    def test_small_steps_slow_samples_and_silly_values_ignored(self):
        b = BatteryMonitor()
        b.update(0.0, 7.6, -0.2)
        b.update(2.0, 7.6, -0.3)            # step below IR_STEP
        b.update(20.0, 7.0, -2.0)           # too long between samples
        b.update(22.0, 6.9, -0.2)           # voltage fell as the load fell: negative resistance
        b.update(24.0, 6.9 - 3.0 * 1.8, -2.0)   # +3 ohm: above the 2 ohm plausibility limit
        self.assertIsNone(b.resistance)

    def test_reset_learning(self):
        b = BatteryMonitor()
        b.learned_capacity_mah, b.resistance, b.resistance_baseline, b.cycle_mah = 2000.0, 0.1, 0.1, 50.0
        b._ir_samples = [0.1]
        b.reset_learning()
        self.assertEqual((b.learned_capacity_mah, b.resistance, b.resistance_baseline, b.cycle_mah, b._ir_samples),
                         (None, None, None, 0.0, []))


class PersistenceTests(unittest.TestCase):
    def test_round_trip_through_json(self):
        a = BatteryMonitor()
        a.update(0.0, 8.2, 0.0, charge_done=True)
        a.update(10.0, 7.9, -1.0)
        a.learned_capacity_mah, a.resistance, a.resistance_baseline = 2700.0, 0.12, 0.11
        d = json.loads(json.dumps(a.to_dict()))
        b = BatteryMonitor()
        b.from_dict(d)
        self.assertEqual(b.to_dict(), a.to_dict())

    def test_restore_without_soc(self):
        b = BatteryMonitor()
        b.from_dict({"soc": 40.0, "remaining_mah": 1000.0, "anchored": True, "cycle_mah": None}, restore_soc=False)
        self.assertIsNone(b.soc)
        self.assertEqual(b.cycle_mah, 0.0)

    def test_restore_from_empty_dict(self):
        b = BatteryMonitor()
        b.from_dict({})
        self.assertIsNone(b.soc)
        self.assertIsNone(b.learned_capacity_mah)


if __name__ == "__main__":
    unittest.main()
