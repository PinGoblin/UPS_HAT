"""ups_hat.board: the UPS class and Snapshot, against the register simulators.

Each fault rule gets its own test: the condition is set up on the simulated chips, the
simulated clock is advanced past the rule's debounce time, and the fault must appear, and
clear again once the condition goes away.
"""

import json
import os
import unittest
from unittest import mock

import helpers
from helpers import BoardTestCase, battery, mains, set_adc
from sim import FakeBQ25798, FakeI2C
from ups_hat import UPS, bq25798 as bq
from ups_hat import board as board_mod
from ups_hat.board import FACTORY_PDOS, Snapshot, _nearest_pd_voltage
from ups_hat.bus import DeviceNotFound, NotSupported
from ups_hat.faults import CRITICAL, INFO, WARNING


class FakePi:
    """Stand-in for ups_hat.pimon.PiPower."""

    available = True

    def __init__(self, throttled=None, ext5v=5.1):
        self.th = throttled or {}
        self.v5 = ext5v
        self.calls = 0

    def throttled(self):
        self.calls += 1
        return dict(self.th)

    def ext5v(self):
        return self.v5


# ---------------------------------------------------------------- construction and connection
class ConstructionTests(BoardTestCase):
    def test_bad_cells_parallel(self):
        for n in (0, 3, "2"):
            with self.subTest(n=n), self.assertRaises(ValueError):
                UPS(FakeI2C(), cells_parallel=n, pi_monitor=False)

    def test_defaults_per_pack(self):
        _, u1 = self.make(cells_parallel=1)
        _, u2 = self.make(cells_parallel=2)
        self.assertEqual((u1.target_charge_current, u2.target_charge_current), (1.5, 2.0))
        self.assertAlmostEqual(u2.battery.nominal_capacity_mah, 2 * u1.battery.nominal_capacity_mah)

    def test_targets_are_clamped(self):
        _, u = self.make(charge_voltage=9.0, charge_current=5.0)
        self.assertEqual((u.target_charge_voltage, u.target_charge_current), (8.4, 3.0))
        _, u = self.make(charge_voltage=5.0, charge_current=0.0)
        self.assertEqual((u.target_charge_voltage, u.target_charge_current), (7.0, 0.1))

    def test_configure_applies_board_settings(self):
        _, u = self.make()
        c = u.charger
        self.assertEqual(c.watchdog_s, 0)
        self.assertTrue(c.adc_enabled and c.ibat_discharge_sensing and c.sfet_present and c.charge_enabled)
        self.assertAlmostEqual(c.charge_voltage, 8.2)
        self.assertAlmostEqual(c.charge_current, 1.5)

    def test_auto_configure_off_leaves_chip_defaults(self):
        _, u = self.make(auto_configure=False)
        self.assertAlmostEqual(u.charger.charge_voltage, 8.4)
        self.assertEqual(u.charger.watchdog_s, 40)

    def test_no_ship_fet(self):
        _, u = self.make(ship_fet=False)
        self.assertFalse(u.charger.sfet_present)
        for method in (u.ship_mode, u.shutdown_mode, u.system_reset):
            with self.subTest(method=method.__name__), self.assertRaises(NotSupported):
                method()

    def test_opens_linux_bus_when_none_given(self):
        with mock.patch.object(board_mod, "open_bus", return_value=FakeI2C()) as ob:
            u = UPS(bus=3, pi_monitor=False)
        ob.assert_called_once_with(3)
        self.assertIsNotNone(u.charger)


class MissingChipTests(BoardTestCase):
    def test_no_chips_does_not_raise(self):
        _, u = self.make(bq=False, pd=False)
        self.assertIsNone(u.charger)
        s = u.poll()
        self.assertFalse(s.charger_ok or s.pd_ok)
        self.assertEqual(set(s.fault_codes()), {"BUS_CHARGER_MISSING", "BUS_PD_MISSING"})
        self.assertEqual(s.worst_severity(), CRITICAL)
        self.assertIn("Charger not responding.", u.report(s))

    def test_methods_needing_a_chip_raise(self):
        _, u = self.make(bq=False, pd=False)
        calls = [lambda: u.charging_enabled, lambda: u.enable_charging(True), lambda: u.set_charge_voltage(8.0),
                 lambda: u.set_charge_current(1.0), lambda: u.set_input_current_limit(1.0), u.configure,
                 u.sync_input_current_limit, u.power_off, u.renegotiate_pd, u.pd_config, u.check_pd_config,
                 u.restore_pd_defaults]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(DeviceNotFound):
                call()

    def test_charger_appears_later(self):
        bus, u = self.make(bq=False)
        self.assertIsNone(u.charger)
        bus.devices[0x6B] = FakeBQ25798()
        mains(bus)
        s = u.poll()
        self.assertTrue(s.charger_ok)
        self.assertAlmostEqual(u.charger.charge_voltage, 8.2, msg="configured on reconnect")
        self.assertFault(s, "CHG_RESET_DETECTED")

    def test_charger_disappears(self):
        bus, u = self.make()
        u.poll()
        del bus.devices[0x6B]
        s = u.poll()
        self.assertFault(s, "BUS_CHARGER_MISSING")
        self.assertIsNone(u.charger)
        self.assertIsNone(s.vbat)

    def test_pd_disappears_and_returns(self):
        bus, u = self.make()
        self.assertTrue(u.poll().pd_ok)
        pd = bus.devices.pop(0x28)
        s = u.poll()
        self.assertFault(s, "BUS_PD_MISSING")
        self.assertTrue(s.charger_ok, "charger still read")
        bus.devices[0x28] = pd
        self.assertNoFault(u.poll(), "BUS_PD_MISSING")


class FlakyBus(FakeI2C):
    """FakeI2C whose reads or writes to chosen addresses fail, as a disturbed I2C bus would."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.fail_reads, self.fail_writes = set(), set()

    def readfrom_mem(self, addr, reg, n):
        if addr in self.fail_reads:
            raise OSError(121, "EREMOTEIO")
        return super().readfrom_mem(addr, reg, n)

    def writeto_mem(self, addr, reg, buf):
        if addr in self.fail_writes:
            raise OSError(121, "EREMOTEIO")
        super().writeto_mem(addr, reg, buf)


class RecoveryTests(BoardTestCase):
    """I2C errors in the middle of a poll are absorbed, never raised."""

    def make_flaky(self, **kw):
        bus = FlakyBus()
        mains(bus)
        bus.stusb.set_attached()
        bus.stusb.set_contract(2, 3.0)
        kw.setdefault("pi_monitor", False)
        return bus, UPS(bus, **kw)

    def test_pd_found_later_and_pd_absent(self):
        _, u = self.make(pd=False)
        self.assertFault(u.poll(), "BUS_PD_MISSING")

    def test_sync_with_pd_read_failure(self):
        bus, u = self.make_flaky()
        bus.fail_reads.add(0x28)
        self.assertIsNone(u.sync_input_current_limit())

    def test_contract_change_while_charger_writes_fail(self):
        bus, u = self.make_flaky()
        u.poll()
        bus.stusb.set_contract(2, 1.5)
        bus.fail_writes.add(0x6B)
        s = u.poll()
        self.assertTrue(s.charger_ok)

    def test_reconfigure_while_charger_writes_fail(self):
        bus, u = self.make_flaky()
        u.poll()
        bus.bq.power_on_reset()
        mains(bus)
        bus.fail_writes.add(0x6B)
        self.clock.advance(61)
        self.assertTrue(u.poll().charger_ok)
        self.assertIsNone(u._reset_detected_at)
        bus.fail_writes.clear()
        self.clock.advance(61)
        self.assertFault(u.poll(), "CHG_RESET_DETECTED")

    def test_settings_lost_detection(self):
        _, u = self.make()
        self.assertFalse(u._settings_lost())
        u.charger.watchdog_s = 40
        self.assertTrue(u._settings_lost())
        u.configure()
        u.charger.sfet_present = False
        self.assertTrue(u._settings_lost())
        u.configure()
        u.charger.adc_enable(False)
        self.assertTrue(u._settings_lost())

    def test_wiring_protection_while_charger_writes_fail(self):
        bus, u = self.make_flaky()
        set_adc(bus, vbat=3800, ibat=0)
        bus.fail_writes.add(0x6B)
        s = self.run_for(u, 12)
        self.assertFault(s, "BAT_WIRING_FAULT")
        self.assertFalse(u._charge_disabled_by_protect, "could not stop charging; will retry")
        bus.fail_writes.clear()
        self.run_for(u, 2)
        self.assertTrue(u._charge_disabled_by_protect)
        bus.fail_writes.add(0x6B)
        set_adc(bus, vbat=7800, ibat=1000)
        u.poll()
        self.assertTrue(u._charge_disabled_by_protect, "could not re-enable; will retry")
        bus.fail_writes.clear()
        u.poll()
        self.assertFalse(u._charge_disabled_by_protect)


# ---------------------------------------------------------------- settings
class SettingTests(BoardTestCase):
    def test_enable_charging(self):
        _, u = self.make()
        u.enable_charging(False)
        self.assertFalse(u.charging_enabled)
        u.enable_charging(True)
        self.assertTrue(u.charging_enabled)

    def test_set_charge_voltage_moves_full_point(self):
        _, u = self.make()
        for volts, expected in ((8.0, 8.0), (9.0, 8.4), (6.0, 7.0)):
            with self.subTest(volts=volts):
                u.set_charge_voltage(volts)
                self.assertAlmostEqual(u.charger.charge_voltage, expected)
                self.assertAlmostEqual(u.battery.full_cell_voltage, expected / 2)

    def test_current_limits_are_clamped(self):
        _, u = self.make()
        u.set_charge_current(5.0)
        self.assertAlmostEqual(u.charger.charge_current, 3.0)
        u.set_input_current_limit(4.0)
        self.assertAlmostEqual(u.charger.input_current_limit, 3.0)
        u.set_input_current_limit(0.0)
        self.assertAlmostEqual(u.charger.input_current_limit, 0.1)

    def test_input_limit_follows_contract_and_rp(self):
        bus, u = self.make()
        cases = [  # (contract amps or None, Rp advertisement, expected limit)
            (3.0, "3.0 A", 3.0), (1.5, "3.0 A", 1.5), (None, "3.0 A", 3.0), (None, "1.5 A", 1.5),
            (None, "default", 0.5), (None, "open", 0.5),
        ]
        for amps, cc, expected in cases:
            with self.subTest(contract=amps, cc=cc):
                bus.stusb.set_attached(cc=cc)
                bus.stusb.set_contract(2 if amps else 0, amps or 0)
                self.assertAlmostEqual(u.sync_input_current_limit(), expected)
                self.assertAlmostEqual(u.charger.input_current_limit, expected)

    def test_input_limit_without_pd_chip(self):
        _, u = self.make(pd=False)
        self.assertIsNone(u.sync_input_current_limit())

    def test_poll_resyncs_on_contract_change(self):
        bus, u = self.make()
        u.poll()
        bus.stusb.set_contract(2, 2.0)
        u.poll()
        self.assertAlmostEqual(u.charger.input_current_limit, 2.0)

    def test_charger_reset_is_detected_and_repaired(self):
        bus, u = self.make()
        u.poll()
        bus.bq.power_on_reset()
        mains(bus)
        self.clock.advance(61)
        s = u.poll()
        self.assertAlmostEqual(u.charger.charge_voltage, 8.2)
        self.assertFault(s, "CHG_RESET_DETECTED")
        self.assertFault(self.run_for(u, 500, step=50), "CHG_RESET_DETECTED")
        self.assertNoFault(self.run_for(u, 120, step=60), "CHG_RESET_DETECTED")

    def test_reset_detected_can_be_acknowledged(self):
        bus, u = self.make()
        u.poll()
        bus.bq.power_on_reset()
        mains(bus)
        self.clock.advance(61)
        self.assertFault(u.poll(), "CHG_RESET_DETECTED")
        u.acknowledge("CHG_RESET_DETECTED")
        self.assertNoFault(u.poll(), "CHG_RESET_DETECTED")

    def test_watchdog_flag_triggers_immediate_check(self):
        bus, u = self.make()
        u.poll()
        bus.bq.power_on_reset()
        mains(bus)
        bus.bq.flags[0] = 0x20                       # WATCHDOG_EXPIRED latched
        self.clock.advance(2)                        # well inside the 60 s check interval
        s = u.poll()
        self.assertAlmostEqual(u.charger.charge_voltage, 8.2)
        self.assertIn("CHG_WATCHDOG_EXPIRED", s.fault_codes())


# ---------------------------------------------------------------- power control
class PowerControlTests(BoardTestCase):
    def test_modes(self):
        bus, u = self.make()
        for method, mode in ((u.ship_mode, bq.SDRV_SHIP), (u.shutdown_mode, bq.SDRV_SHUTDOWN),
                             (u.system_reset, bq.SDRV_SYSTEM_RESET)):
            with self.subTest(method=method.__name__):
                bus.bq.r[0x11] &= ~0x06
                method()
                self.assertEqual(u.charger.ship_fet_control, mode)
                self.assertEqual(bus.bq.r[0x11] & 1, 1, "no delay")
        u.ship_mode(delay=True)
        self.assertEqual(bus.bq.r[0x11] & 1, 0)

    def test_power_off_table(self):
        cases = [  # (adapter, low_battery, result, SDRV mode)
            (False, False, "ship", bq.SDRV_SHIP), (False, True, "ship", bq.SDRV_SHIP),
            (True, True, "reset", bq.SDRV_SYSTEM_RESET), (True, False, "none", bq.SDRV_IDLE),
        ]
        for adapter, low, result, mode in cases:
            with self.subTest(adapter=adapter, low_battery=low):
                bus, u = self.make()
                (mains if adapter else battery)(bus)
                self.assertEqual(u.power_off(low_battery=low), result)
                self.assertEqual(u.charger.ship_fet_control, mode)

    def test_power_off_remembers_low_battery_shutdown(self):
        bus, u = self.make()
        battery(bus, vbat=6.1 * 1000, ibat=-1500)
        self.assertTrue(u.poll().should_shutdown)
        mains(bus)                                   # adapter back before the hook runs
        self.assertEqual(u.power_off(), "reset")

    def test_power_off_saves_clean_state(self):
        path = self.path("state.json")
        bus, u = self.make(state_file=path)
        u.poll()
        battery(bus)
        u.power_off()
        with open(path) as f:
            self.assertTrue(json.load(f)["clean_shutdown"])


# ---------------------------------------------------------------- USB-C PD
class PdTests(BoardTestCase):
    def test_renegotiate(self):
        bus, u = self.make()
        u.renegotiate_pd()
        self.assertEqual(bus.stusb.soft_resets, 1)

    def test_pd_config(self):
        _, u = self.make()
        cfg = u.pd_config()
        self.assertEqual((cfg["ram_count"], cfg["nvm_count"]), (3, 3))
        self.assertEqual([tuple(round(x, 2) for x in p) for p in cfg["ram"]], [tuple(p) for p in FACTORY_PDOS])
        self.assertEqual(len(cfg["nvm"]), 3)

    def test_check_pd_config(self):
        bus, u = self.make()
        self.assertTrue(u.check_pd_config())
        u.pd.set_sink_pdo(3, 12.0, 3.0)
        self.assertFalse(u.check_pd_config())
        u.restore_pd_defaults()
        self.assertTrue(u.check_pd_config())
        u.pd.pdo_count = 2
        self.assertFalse(u.check_pd_config())

    def test_restore_defaults(self):
        bus, u = self.make()
        u.pd.set_sink_pdo(2, 12.0, 1.0)
        u.restore_pd_defaults()
        self.assertTrue(u.check_pd_config())
        self.assertEqual((bus.stusb.soft_resets, bus.stusb.nvm_writes), (1, 0))
        u.restore_pd_defaults(write_nvm=True)
        self.assertEqual(bus.stusb.nvm_writes, 5)

    def test_config_mismatch_checked_hourly(self):
        bus, u = self.make()
        u.pd.set_sink_pdo(3, 20.0, 3.0)
        self.assertFault(u.poll(), "PD_CONFIG_MISMATCH")
        u.restore_pd_defaults()
        self.assertFault(self.run_for(u, 60, step=30), "PD_CONFIG_MISMATCH", "not re-checked yet")
        self.clock.advance(3600)
        self.assertNoFault(u.poll(), "PD_CONFIG_MISMATCH")


# ---------------------------------------------------------------- snapshot and derived values
class SnapshotTests(BoardTestCase):
    def test_empty_snapshot(self):
        s = Snapshot()
        self.assertEqual(s.fault_codes(), [])
        self.assertEqual(s.worst_severity(), -1)
        self.assertFalse(s.should_shutdown)

    def test_mains_values(self):
        _, u = self.make()
        s = u.poll()
        self.assertTrue(s.charger_ok and s.pd_ok and s.adapter_present and s.power_good and s.charging)
        self.assertFalse(s.on_battery)
        self.assertEqual(s.charge_state, bq.CHG_FAST)
        self.assertAlmostEqual(s.input_power, 9.0 * 1.2)
        self.assertAlmostEqual(s.battery_power, -7.8 * 1.0)
        self.assertAlmostEqual(s.output_power, (10.8 * 0.95 - 7.8) * 0.93 - 0.15)
        self.assertEqual((s.contract_voltage, s.contract_current), (9.0, 3.0))
        self.assertIsNotNone(s.time_to_full_h)
        self.assertIsNone(s.time_to_empty_h)
        self.assertEqual(s.pd["contract"], repr(s.contract))
        self.assertEqual(s.pd["events"], [])

    def test_battery_values(self):
        bus, u = self.make()
        battery(bus)
        s = u.poll()
        self.assertTrue(s.on_battery and s.battery_present)
        self.assertFalse(s.adapter_present or s.charging)
        self.assertEqual(s.input_power, 0.0)
        self.assertAlmostEqual(s.battery_power, 7.6 * 1.5)
        self.assertIsNone(s.contract_voltage)
        self.assertIsNotNone(s.time_to_empty_h)

    def test_to_dict_is_json(self):
        _, u = self.make()
        d = u.poll().to_dict()
        self.assertEqual(json.loads(json.dumps(d))["vbat"], d["vbat"])
        self.assertNotIn("adc", d)
        self.assertNotIn("contract", d)

    def test_nearest_pd_voltage(self):
        for v, expected in ((5.1, 5.0), (8.6, 9.0), (11.4, 12.0), (13.6, 15.0), (19.0, 20.0),
                            (3.0, None), (25.0, None)):
            with self.subTest(v=v):
                self.assertEqual(_nearest_pd_voltage(v), expected)


# ---------------------------------------------------------------- fault rules
class ChargerFaultTests(BoardTestCase):
    def test_live_faults_map_to_codes(self):
        cases = [(0x40, 0, "CHG_VBUS_OVP"), (0x20, 0, "CHG_VBAT_OVP"), (0x10, 0, "CHG_IBUS_OCP"),
                 (0x08, 0, "CHG_IBAT_OCP"), (0x04, 0, "CHG_CONVERTER_OCP"), (0x01, 0, "CHG_VAC_OVP"),
                 (0x02, 0, "CHG_VAC_OVP"), (0x80, 0, "CHG_IBAT_REGULATION"), (0, 0x80, "CHG_VSYS_SHORT"),
                 (0, 0x40, "CHG_VSYS_OVP"), (0, 0x04, "CHG_THERMAL_SHUTDOWN")]
        for f0, f1, code in cases:
            with self.subTest(code=code):
                bus, u = self.make()
                bus.bq.set_status(fault0=f0, fault1=f1)
                s = u.poll()
                self.assertFault(s, code)
                self.assertFalse([f for f in s.faults if f.code == code][0].transient)

    def test_latched_only_fault_is_transient(self):
        bus, u = self.make()
        u.poll()
        bus.bq.flags[4] = 0x40                       # VBUS_OVP came and went
        s = u.poll()
        f = [f for f in s.faults if f.code == "CHG_VBUS_OVP"][0]
        self.assertTrue(f.transient)
        self.assertIn(f, s.new_faults)
        self.assertNotIn("CHG_VBUS_OVP", [f.code for f in u.faults], "transients are not 'active'")
        self.assertNoFault(u.poll(), "CHG_VBUS_OVP")

    def test_status_faults(self):
        cases = [(dict(s3=0x08), "CHG_TIMER_EXPIRED"), (dict(s3=0x02), "CHG_PRECHARGE_TIMER_EXPIRED"),
                 (dict(s3=0x04), "CHG_TRICKLE_TIMER_EXPIRED"), (dict(extra0=0x10), "CHG_POOR_SOURCE"),
                 (dict(extra0=0x20), "CHG_WATCHDOG_EXPIRED")]
        for kw, code in cases:
            with self.subTest(code=code):
                bus, u = self.make()
                bus.bq.set_status(**kw)
                self.assertFault(u.poll(), code)

    def test_thermal_regulation(self):
        bus, u = self.make()
        bus.bq.r[0x1D] |= 0x04
        s = u.poll()
        self.assertFault(s, "CHG_THERMAL_REGULATION")
        self.assertNoFault(s, "BAT_CHARGE_BLOCKED")

    def test_input_limited_after_30_s(self):
        bus, u = self.make()
        bus.bq.set_status(extra0=0x80)               # IINDPM
        self.assertNoFault(self.run_for(u, 20), "CHG_INPUT_LIMITED")
        self.assertFault(self.run_for(u, 12), "CHG_INPUT_LIMITED")
        bus.bq.set_status()
        self.assertNoFault(u.poll(), "CHG_INPUT_LIMITED")


class BatteryFaultTests(BoardTestCase):
    def test_absent(self):
        bus, u = self.make()
        bus.bq.set_status(vbat_present=False)
        set_adc(bus, vbat=0, ibat=0)
        self.assertNoFault(u.poll(), "BAT_ABSENT")
        self.assertFault(self.run_for(u, 6), "BAT_ABSENT")

    def test_wiring_fault_stops_charging_then_restores(self):
        bus, u = self.make()
        set_adc(bus, vbat=3800, ibat=0)
        s = self.run_for(u, 12)
        self.assertFault(s, "BAT_WIRING_FAULT")
        self.assertFalse(u.charger.charge_enabled, "protect=True stops charging")
        u.enable_charging(True)                      # remembered, not applied
        self.assertFalse(u.charger.charge_enabled)
        set_adc(bus, vbat=7800, ibat=1000)
        s = u.poll()
        self.assertNoFault(s, "BAT_WIRING_FAULT")
        self.assertTrue(u.charger.charge_enabled)

    def test_wiring_fault_without_protect(self):
        bus, u = self.make(protect=False)
        set_adc(bus, vbat=3800, ibat=0)
        self.assertFault(self.run_for(u, 12), "BAT_WIRING_FAULT")
        self.assertTrue(u.charger.charge_enabled)

    def test_deeply_discharged(self):
        bus, u = self.make()
        set_adc(bus, vbat=5500, ibat=100)
        self.assertFault(self.run_for(u, 12), "BAT_DEEPLY_DISCHARGED")

    def test_critical_by_voltage(self):
        bus, u = self.make()
        battery(bus, vbat=6100)
        s = u.poll()
        self.assertTrue(s.should_shutdown)
        self.assertFault(s, "BAT_CRITICAL")
        self.assertEqual(s.faults[0].severity, CRITICAL, "most severe first")

    def test_custom_low_battery_voltage(self):
        bus, u = self.make(low_battery_voltage=6.5)
        battery(bus, vbat=6400)
        self.assertTrue(u.poll().should_shutdown)

    def test_low_and_critical_by_soc(self):
        bus, u = self.make()
        battery(bus, vbat=7000, ibat=-500)
        u.poll()
        for soc, code in ((12.0, "BAT_LOW"), (4.0, "BAT_CRITICAL")):
            with self.subTest(soc=soc):
                u.battery.soc = soc
                u.battery.remaining_mah = u.battery.capacity_mah * soc / 100
                self.clock.advance(2)
                s = u.poll()
                self.assertFault(s, code)
                self.assertEqual(s.should_shutdown, code == "BAT_CRITICAL")

    def test_shutdown_flag_clears_on_mains(self):
        bus, u = self.make()
        battery(bus, vbat=6100)
        u.poll()
        mains(bus)
        self.clock.advance(2)
        self.assertFalse(u.poll().should_shutdown)
        self.assertEqual(u.power_off(), "none")

    def test_charge_blocked(self):
        bus, u = self.make()
        set_adc(bus, vbat=7400, ibat=0)
        self.assertNoFault(self.run_for(u, 100), "BAT_CHARGE_BLOCKED")
        s = self.run_for(u, 30)
        self.assertFault(s, "BAT_CHARGE_BLOCKED")
        self.assertNoFault(s, "BAT_IMBALANCE_SUSPECTED")

    def test_charge_blocked_near_full_suggests_imbalance(self):
        bus, u = self.make()
        set_adc(bus, vbat=7800, ibat=0)
        s = self.run_for(u, 130)
        self.assertFault(s, "BAT_CHARGE_BLOCKED")
        self.assertFault(s, "BAT_IMBALANCE_SUSPECTED")

    def test_not_blocked_when_user_stopped_charging(self):
        bus, u = self.make()
        u.enable_charging(False)
        set_adc(bus, vbat=7400, ibat=0)
        self.assertNoFault(self.run_for(u, 130), "BAT_CHARGE_BLOCKED")

    def test_repeated_early_charge_stops(self):
        bus, u = self.make()
        for _ in range(2):
            set_adc(bus, vbat=7600, ibat=1000)
            self.run_for(u, 2)
            set_adc(bus, vbat=7600, ibat=0)
            s = self.run_for(u, 2)
        self.assertFault(s, "BAT_IMBALANCE_SUSPECTED")
        self.assertEqual(u._charge_stop_events, 2)
        u.acknowledge("BAT_IMBALANCE_SUSPECTED")
        self.assertEqual(u._charge_stop_events, 0)

    def test_high_resistance(self):
        cases = [(1, 0.40, None, True), (1, 0.30, None, False), (2, 0.25, None, True),
                 (1, 0.20, 0.10, True), (1, 0.15, 0.10, False)]
        for parallel, r, baseline, expected in cases:
            with self.subTest(parallel=parallel, r=r, baseline=baseline):
                _, u = self.make(cells_parallel=parallel)
                u.battery.resistance, u.battery.resistance_baseline = r, baseline
                s = u.poll()
                self.assertEqual("BAT_HIGH_RESISTANCE" in s.fault_codes(), expected)

    def test_capacity_rules(self):
        cases = [(1, 0.65, "BAT_CAPACITY_LOW"), (1, 0.80, None), (2, 0.50, "BAT_PARALLEL_CELL_MISSING"),
                 (2, 0.65, "BAT_CAPACITY_LOW")]
        for parallel, ratio, code in cases:
            with self.subTest(parallel=parallel, ratio=ratio):
                _, u = self.make(cells_parallel=parallel)
                u.battery.learned_capacity_mah = ratio * u.battery.nominal_capacity_mah
                codes = u.poll().fault_codes()
                for c in ("BAT_CAPACITY_LOW", "BAT_PARALLEL_CELL_MISSING"):
                    self.assertEqual(c in codes, c == code)

    def test_self_discharge(self):
        bus, u = self.make()
        for _ in range(3):                           # done -> recharge, three times in a few hours
            bus.bq.set_status(chg=bq.CHG_DONE)
            set_adc(bus, ibat=0)
            self.run_for(u, 1800, step=300)
            bus.bq.set_status(chg=bq.CHG_FAST)
            set_adc(bus, ibat=1000)
            s = self.run_for(u, 600, step=300)
        self.assertFault(s, "BAT_SELF_DISCHARGE")
        u.acknowledge("BAT_SELF_DISCHARGE")
        self.assertNoFault(u.poll(), "BAT_SELF_DISCHARGE")


class BoardFaultTests(BoardTestCase):
    def test_ts_out_of_window(self):
        for ts, expected in ((614, False), (400, True), (800, True)):
            with self.subTest(ts=ts):
                bus, u = self.make()
                set_adc(bus, ts=ts)
                self.assertEqual("BOARD_TS_FAULT" in self.run_for(u, 8).fault_codes(), expected)

    def test_ts_status_bit(self):
        bus, u = self.make()
        bus.bq.r[0x1F] = 0x01                        # TS_HOT
        self.assertFault(self.run_for(u, 8), "BOARD_TS_FAULT")

    def test_temperatures(self):
        for raw, code in ((160, None), (180, "BOARD_HOT"), (220, "BOARD_OVERHEAT")):   # 0.5 C per LSB
            with self.subTest(tdie=raw / 2):
                bus, u = self.make()
                set_adc(bus, tdie=raw)
                codes = u.poll().fault_codes()
                self.assertEqual("BOARD_HOT" in codes, code == "BOARD_HOT")
                self.assertEqual("BOARD_OVERHEAT" in codes, code == "BOARD_OVERHEAT")

    def test_adapter_insufficient(self):
        bus, u = self.make()
        set_adc(bus, ibat=-500)
        self.assertNoFault(self.run_for(u, 20), "ADAPTER_INSUFFICIENT")
        self.assertFault(self.run_for(u, 12), "ADAPTER_INSUFFICIENT")

    def test_cable_resistance(self):
        bus, u = self.make()
        set_adc(bus, vbus=8100, ibus=2000)           # 0.9 V lost at 2 A on a 9 V contract
        self.assertFault(self.run_for(u, 32), "CABLE_RESISTANCE_HIGH")
        set_adc(bus, ibus=1000)                      # too little current to judge: timer resets
        self.assertNoFault(u.poll(), "CABLE_RESISTANCE_HIGH")

    def test_output_overload(self):
        bus, u = self.make()
        battery(bus, vbat=7000, ibat=-4000)          # 28 W from the pack
        self.assertFault(self.run_for(u, 12), "OUTPUT_OVERLOAD")


class PdFaultTests(BoardTestCase):
    def test_cc_overvoltage(self):
        bus, u = self.make()
        bus.stusb.r[0x13] = 0x80 | 0x40
        self.assertFault(u.poll(), "PD_CC_OVERVOLTAGE")

    def test_no_contract(self):
        bus, u = self.make()
        bus.stusb.set_contract(0, 0)
        self.assertFault(self.run_for(u, 12), "PD_NO_CONTRACT")

    def test_capability_mismatch(self):
        bus, u = self.make()
        bus.stusb.set_contract(2, 3.0, mismatch=True)
        self.assertFault(u.poll(), "PD_CAPABILITY_MISMATCH")

    def test_low_contract(self):
        bus, u = self.make()
        set_adc(bus, vbus=5000)
        self.assertFault(self.run_for(u, 12), "PD_LOW_CONTRACT")


class PiFaultTests(BoardTestCase):
    def make_pi(self, **kw):
        bus, u = self.make()
        u.pi = FakePi(**kw)
        return bus, u

    def test_undervoltage_now_and_since_boot(self):
        _, u = self.make_pi(throttled={"under_voltage": True, "under_voltage_occurred": True})
        s = u.poll()
        self.assertFault(s, "PI_UNDERVOLTAGE")
        self.assertNoFault(s, "PI_UNDERVOLTAGE_OCCURRED")
        _, u = self.make_pi(throttled={"under_voltage_occurred": True})
        self.assertFault(u.poll(), "PI_UNDERVOLTAGE_OCCURRED")

    def test_output_5v_fault(self):
        _, u = self.make_pi(ext5v=4.5)
        self.assertFault(self.run_for(u, 12), "OUTPUT_5V_FAULT")

    def test_external_supply(self):
        bus, u = self.make_pi(ext5v=5.1)
        set_adc(bus, ibus=100, ibat=0)               # board delivers almost nothing
        self.assertFault(self.run_for(u, 70, step=5), "PI_EXTERNAL_SUPPLY")

    def test_pi_readings_cached_for_10_s(self):
        _, u = self.make_pi(ext5v=5.05)
        self.run_for(u, 30, step=1)
        self.assertLessEqual(u.pi.calls, 4)
        self.assertIn("Pi 5 V input : 5.05 V", u.report())

    def test_pi_monitor_detection(self):
        with mock.patch("ups_hat.pimon.PiPower") as cls:
            cls.return_value.available = False
            _, u = self.make(pi_monitor=True)
            self.assertIsNone(u.pi)
            cls.return_value.available = True
            _, u = self.make(pi_monitor=True)
            self.assertIs(u.pi, cls.return_value)
            cls.side_effect = RuntimeError("no vcgencmd")
            _, u = self.make(pi_monitor=True)
            self.assertIsNone(u.pi)


# ---------------------------------------------------------------- fault bookkeeping and callbacks
class CallbackTests(BoardTestCase):
    def test_new_and_cleared_callbacks(self):
        bus, u = self.make()
        new, cleared = [], []

        def on_new(f):
            new.append(f)
        self.assertIs(u.on_fault(on_new), on_new, "returns the function (decorator use)")
        u.on_clear(cleared.append)
        set_adc(bus, tdie=180)
        u.poll()
        u.poll()
        self.assertEqual([f.code for f in new], ["BOARD_HOT"], "reported once while active")
        set_adc(bus, tdie=60)
        s = u.poll()
        self.assertEqual([f.code for f in cleared], ["BOARD_HOT"])
        self.assertEqual([f.code for f in s.cleared_faults], ["BOARD_HOT"])

    def test_decorator_form(self):
        bus, u = self.make()
        seen = []

        @u.on_fault
        def alert(fault):
            seen.append(fault.code)

        battery(bus, vbat=6100)
        u.poll()
        self.assertIn("BAT_CRITICAL", seen)

    def test_since_is_kept_and_data_updated(self):
        bus, u = self.make()
        set_adc(bus, tdie=180)
        t0 = u.poll().faults[0].since
        set_adc(bus, tdie=190)
        self.clock.advance(5)
        f = [f for f in u.poll().faults if f.code == "BOARD_HOT"][0]
        self.assertEqual(f.since, t0)
        self.assertEqual(f.data["tdie"], 95.0)

    def test_severity_order(self):
        bus, u = self.make()
        battery(bus, vbat=6100, tdie=180)
        sev = [f.severity for f in u.poll().faults]
        self.assertEqual(sev, sorted(sev, reverse=True))
        self.assertIn(WARNING, sev)
        self.assertNotIn(INFO, sev[:1])

    def test_run(self):
        _, u = self.make()
        got = []
        with mock.patch.object(board_mod, "sleep_ms") as sleep:
            u.run(interval_s=0.5, callback=got.append, count=3)
        self.assertEqual(len(got), 3)
        self.assertTrue(all(isinstance(s, Snapshot) for s in got))
        sleep.assert_called_with(500)
        with mock.patch.object(board_mod, "sleep_ms"):
            u.run(count=1)


# ---------------------------------------------------------------- state file
class StateFileTests(BoardTestCase):
    def test_round_trip(self):
        path = self.path("state.json")
        _, a = self.make(state_file=path)
        a.battery.learned_capacity_mah, a.battery.resistance_baseline = 2600.0, 0.12
        a.poll()
        a.save_state()
        _, b = self.make(state_file=path)
        self.assertEqual(b.battery.learned_capacity_mah, 2600.0)
        self.assertEqual(b.battery.resistance_baseline, 0.12)
        self.assertFalse(os.path.exists(path + ".tmp"))

    def test_poll_saves_every_five_minutes(self):
        path = self.path("state.json")
        _, u = self.make(state_file=path)
        u.poll()
        first = u._last_save
        self.assertIsNotNone(first)
        self.run_for(u, 200, step=50)
        self.assertEqual(u._last_save, first)
        self.run_for(u, 200, step=50)
        self.assertGreater(u._last_save, first)

    def write_state(self, path, **d):
        with open(path, "w") as f:
            json.dump(d, f)

    def test_early_cutoff_reported_after_power_loss(self):
        path = self.path("state.json")
        self.write_state(path, battery={"anchored": True}, clean_shutdown=False,
                         last={"on_battery": True, "vbat": 7.2, "soc": 40.0})
        _, u = self.make(state_file=path)
        self.assertFalse(u.battery.anchored)
        s = u.poll()
        self.assertFault(s, "BAT_EARLY_CUTOFF")
        self.assertEqual([f for f in s.faults if f.code == "BAT_EARLY_CUTOFF"][0].data["last_vbat"], 7.2)
        u.acknowledge("BAT_EARLY_CUTOFF")
        self.assertNoFault(u.poll(), "BAT_EARLY_CUTOFF")

    def test_no_early_cutoff(self):
        cases = [dict(clean_shutdown=True, last={"on_battery": True, "vbat": 7.2}),
                 dict(clean_shutdown=False, last={"on_battery": True, "vbat": 6.4}),
                 dict(clean_shutdown=False, last={"on_battery": False, "vbat": 7.9}),
                 dict(clean_shutdown=False, last={})]
        for d in cases:
            with self.subTest(d=d):
                path = self.path("s.json")
                self.write_state(path, **d)
                _, u = self.make(state_file=path)
                self.assertNoFault(u.poll(), "BAT_EARLY_CUTOFF")

    def test_bad_or_missing_files_are_ignored(self):
        path = self.path("bad.json")
        with open(path, "w") as f:
            f.write("{not json")
        _, u = self.make(state_file=path)
        u.poll()
        _, u = self.make(state_file=self.path("missing.json"))
        u.poll()
        _, u = self.make(state_file=os.path.join(self.tmp, "no", "such", "dir", "state.json"))
        u.poll()
        u.save_state()
        self.assertIsNone(u._last_save, "unwritable path: no save, no exception")

    def test_rename_failure_falls_back_to_direct_write(self):
        path = self.path("state.json")
        _, u = self.make(state_file=path)
        u.poll()
        with mock.patch("os.rename", side_effect=OSError):
            u.save_state(clean=True)
        with open(path) as f:
            self.assertTrue(json.load(f)["clean_shutdown"])

    def test_no_state_file(self):
        _, u = self.make()
        u.poll()
        u.save_state()
        self.assertIsNone(u._last_save)

    def test_new_cells_fitted(self):
        path = self.path("state.json")
        _, u = self.make(state_file=path)
        u.poll()
        u.battery.learned_capacity_mah = 2000.0
        u._charge_stop_events = 3
        u._recharge_intervals = [100.0]
        u.new_cells_fitted()
        self.assertIsNone(u.battery.learned_capacity_mah)
        self.assertIsNone(u.battery.soc)
        self.assertFalse(u.battery.anchored)
        self.assertEqual((u._charge_stop_events, u._recharge_intervals, u._boot_events), (0, [], []))
        self.assertIsNotNone(u.poll().soc, "re-estimated from voltage")

    def test_acknowledge_ignores_other_codes(self):
        _, u = self.make()
        u.acknowledge("BOARD_HOT")


# ---------------------------------------------------------------- report
class ReportTests(BoardTestCase):
    def test_mains_report(self):
        _, u = self.make()
        text = u.report()
        for line in ("Power source : adapter", "Input        : 9.00 V  1.20 A  (10.8 W)",
                     "USB-C PD     : 9 V contract, 3.00 A", "Battery      : 7.80 V  +1.00 A",
                     "Time to full :", "System rail  : 7.90 V", "Charger temp : 30.0 C",
                     "Capacity     : {:.0f} mAh (rated)".format(u.battery.nominal_capacity_mah),
                     "Faults       : none"):
            with self.subTest(line=line):
                self.assertIn(line, text)
        self.assertNotIn("Time to empty", text)

    def test_battery_report_with_faults(self):
        bus, u = self.make(low_battery_voltage=7.1)   # critical by voltage, charge still left
        battery(bus, vbat=7000)
        u.battery.learned_capacity_mah = 2900.0
        u.battery.resistance = 0.1
        text = u.report()
        for line in ("Power source : battery", "Time to empty:", "Faults:", "[CRITICAL] BAT_CRITICAL", "    -> ",
                     "Capacity     : 2900 mAh (measured)", "Batt. path R : 100 mOhm"):
            with self.subTest(line=line):
                self.assertIn(line, text)

    def test_report_of_given_snapshot_does_not_poll(self):
        _, u = self.make()
        s = u.poll()
        with mock.patch.object(u, "poll") as poll:
            u.report(s)
        poll.assert_not_called()


if __name__ == "__main__":
    unittest.main()
