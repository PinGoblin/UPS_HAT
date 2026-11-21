"""Scenario tests against the register simulators.

    python3 tests/test_ups_hat.py
    micropython tests/test_ups_hat.py
"""

import sys
sys.path.insert(0, ".")
sys.path.insert(0, "tests")

import ups_hat
from ups_hat import board as board_mod
from ups_hat import UPS, STUSB4500, FACTORY_PDOS
from ups_hat.faults import CRITICAL, WARNING
from sim import FakeI2C


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


CLOCK = Clock()
board_mod.now_s = CLOCK


def make(**kw):
    bus = FakeI2C(**{k: kw.pop(k) for k in ("bq", "pd") if k in kw})
    if bus.bq:
        bus.bq.set_status(vbus=True, pg=True, chg=3)
        bus.bq.adc.update(vbus=9000, ibus=1200, vbat=7800, ibat=1000, vsys=7900)
    if bus.stusb:
        bus.stusb.set_attached()
        bus.stusb.set_contract(2, 3.0)
    kw.setdefault("pi_monitor", False)
    return bus, UPS(bus, **kw)


def run_for(ups, seconds, step=2.0):
    s = None
    end = CLOCK.t + seconds
    while CLOCK.t < end:
        CLOCK.t += step
        s = ups.poll()
    return s


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def configure_writes_board_settings():
    bus, ups = make()
    r = bus.bq.r
    assert r[0x10] & 0x07 == 0, "watchdog disabled"
    assert (r[0x01] << 8 | r[0x02]) == 820, "VREG 8.20 V"
    assert (r[0x03] << 8 | r[0x04]) == 150, "ICHG 1.5 A for 2S1P"
    assert r[0x14] & 0x80 and r[0x14] & 0x20, "SFET_PRESENT and EN_IBAT"
    assert r[0x2E] & 0x80 and (r[0x2E] >> 4) & 3 == 0, "ADC on, 15-bit"
    _, ups2 = make(cells_parallel=2)
    assert abs(ups2.charger.charge_current - 2.0) < 1e-6


@test
def normal_charging_has_no_faults():
    bus, ups = make()
    s = run_for(ups, 10)
    assert s.charger_ok and s.pd_ok
    assert abs(s.vbat - 7.8) < 1e-6 and abs(s.ibat - 1.0) < 1e-6
    assert s.charging and not s.on_battery
    assert s.contract_voltage == 9.0 and abs(s.contract_current - 3.0) < 1e-6
    assert s.faults == [], s.fault_codes()
    assert abs(s.tdie - 30.0) < 1e-6
    assert abs(bus.bq.r[0x06] << 8 | bus.bq.r[0x07]) == 300, "IINDPM synced to 3 A contract"


@test
def signed_adc_values():
    bus, ups = make()
    bus.bq.adc.update(ibat=-1500 & 0xFFFF, tdie=-10 & 0xFFFF)
    s = run_for(ups, 2)
    assert abs(s.ibat + 1.5) < 1e-6 and abs(s.tdie + 5.0) < 1e-6


@test
def charger_fault_and_transient_flag():
    bus, ups = make()
    run_for(ups, 4)
    bus.bq.set_status(fault0=0x20)              # VBAT_OVP active
    s = run_for(ups, 2)
    f = [x for x in s.faults if x.code == "CHG_VBAT_OVP"]
    assert f and f[0].severity == CRITICAL and not f[0].transient
    bus.bq.set_status(fault0=0)
    bus.bq.flags[4] = 0x10                      # IBUS_OCP came and went
    s = run_for(ups, 2)
    f = [x for x in s.faults if x.code == "CHG_IBUS_OCP"]
    assert f and f[0].transient
    assert "CHG_VBAT_OVP" in [x.code for x in s.cleared_faults]
    s = run_for(ups, 2)
    assert "CHG_IBUS_OCP" not in s.fault_codes()


@test
def wiring_fault_stops_and_resumes_charging():
    bus, ups = make()
    bus.bq.adc.update(vbat=3900, ibat=0)
    s = run_for(ups, 14)
    assert "BAT_WIRING_FAULT" in s.fault_codes()
    assert not bus.bq.r[0x0F] & 0x20, "charging disabled"
    bus.bq.adc.update(vbat=7400)
    s = run_for(ups, 4)
    assert "BAT_WIRING_FAULT" not in s.fault_codes()
    assert bus.bq.r[0x0F] & 0x20, "charging re-enabled"


@test
def low_battery_requests_shutdown():
    bus, ups = make()
    bus.bq.set_status(vbus=False, pg=False, chg=0)
    bus.bq.adc.update(vbus=0, ibus=0, vbat=6150, ibat=-2000 & 0xFFFF)
    s = run_for(ups, 4)
    assert s.on_battery and s.should_shutdown
    assert "BAT_CRITICAL" in s.fault_codes()
    assert ups.power_off() == "ship"
    assert (bus.bq.r[0x11] >> 1) & 3 == 2 and bus.bq.r[0x11] & 1, "ship mode, no delay"


@test
def power_off_on_mains():
    bus, ups = make()
    run_for(ups, 2)
    assert ups.power_off() == "none"
    assert ups.power_off(low_battery=True) == "reset"
    assert (bus.bq.r[0x11] >> 1) & 3 == 3


@test
def ship_mode_needs_ship_fet():
    bus, ups = make(ship_fet=False)
    try:
        ups.ship_mode()
        raise AssertionError("expected NotSupported")
    except ups_hat.NotSupported:
        pass


@test
def charge_blocked_and_imbalance():
    bus, ups = make()
    bus.bq.set_status(chg=0)
    bus.bq.adc.update(vbat=7900, ibat=0, ibus=300)
    s = run_for(ups, 130)
    codes = s.fault_codes()
    assert "BAT_CHARGE_BLOCKED" in codes and "BAT_IMBALANCE_SUSPECTED" in codes, codes


@test
def early_charge_stops_counted():
    bus, ups = make()
    for _ in range(2):
        bus.bq.set_status(chg=3)
        bus.bq.adc.update(vbat=7700, ibat=1500)
        run_for(ups, 4)
        bus.bq.set_status(chg=0)
        bus.bq.adc.update(vbat=7650, ibat=0)
        s = run_for(ups, 2)
    assert "BAT_IMBALANCE_SUSPECTED" in s.fault_codes()
    ups.acknowledge("BAT_IMBALANCE_SUSPECTED")
    bus.bq.set_status(chg=3)
    bus.bq.adc.update(ibat=1000)
    s = run_for(ups, 2)
    assert "BAT_IMBALANCE_SUSPECTED" not in s.fault_codes()


@test
def charger_reset_is_detected_and_repaired():
    bus, ups = make()
    run_for(ups, 4)
    bus.bq.power_on_reset()
    bus.bq.set_status()
    s = run_for(ups, 62)
    assert "CHG_RESET_DETECTED" in s.fault_codes()
    assert (bus.bq.r[0x01] << 8 | bus.bq.r[0x02]) == 820 and bus.bq.r[0x10] & 7 == 0


@test
def adapter_insufficient_and_overload():
    bus, ups = make()
    bus.bq.adc.update(vbus=8700, ibus=3000, ibat=-600 & 0xFFFF)
    s = run_for(ups, 34)
    assert "ADAPTER_INSUFFICIENT" in s.fault_codes()
    assert "OUTPUT_OVERLOAD" in s.fault_codes(), s.output_power
    assert "CABLE_RESISTANCE_HIGH" not in s.fault_codes()
    bus.bq.adc.update(vbus=8100, ibus=2500)
    s = run_for(ups, 34)
    assert "CABLE_RESISTANCE_HIGH" in s.fault_codes()


@test
def pd_conditions():
    bus, ups = make()
    bus.stusb.set_contract(0, 0)
    bus.bq.adc.update(vbus=5000)
    s = run_for(ups, 12)
    assert "PD_NO_CONTRACT" in s.fault_codes()
    assert abs((bus.bq.r[0x06] << 8 | bus.bq.r[0x07]) - 300) == 0, "Rp 3.0 A sets 3 A"
    bus.stusb.set_contract(1, 3.0, mismatch=True)
    s = run_for(ups, 12)
    codes = s.fault_codes()
    assert "PD_CAPABILITY_MISMATCH" in codes and "PD_LOW_CONTRACT" in codes, codes
    bus.stusb.r[0x13] = 0x80
    s = run_for(ups, 2)
    assert "PD_CC_OVERVOLTAGE" in s.fault_codes()


@test
def pd_config_check_and_restore():
    bus, ups = make()
    assert ups.check_pd_config()
    bus.stusb.set_pdo(3, 12.0, 2.0)
    assert not ups.check_pd_config()
    ups.restore_pd_defaults()
    assert ups.check_pd_config() and bus.stusb.soft_resets == 1


@test
def nvm_roundtrip():
    bus, ups = make()
    pd = ups.pd
    sectors = pd.read_nvm()
    assert len(sectors) == 5 and sectors[3][1] == 0x19
    new = STUSB4500.encode_nvm_pdos(sectors, FACTORY_PDOS, 3)
    pd.write_nvm(new, confirm=True)
    n, pdos = STUSB4500.decode_nvm_pdos(pd.read_nvm())
    assert n == 3, n
    for (v, a), (fv, fa) in zip(pdos, FACTORY_PDOS):
        assert abs(v - fv) < 0.01 and abs(a - fa) < 0.01, pdos
    assert bus.stusb.r[0x95] == 0, "password cleared"
    try:
        pd.write_nvm(new)
        raise AssertionError("needs confirm")
    except ups_hat.UPSError:
        pass


@test
def resistance_estimate():
    bus, ups = make()
    R = 0.120
    for k in range(30):
        i = 2.0 if k % 2 else 0.2
        bus.bq.set_status(vbus=False, pg=False, chg=0)
        bus.bq.adc.update(vbus=0, ibus=0, ibat=int(-i * 1000) & 0xFFFF, vbat=int((7.6 - R * i) * 1000))
        CLOCK.t += 2
        s = ups.poll()
    assert abs(s.battery_resistance - R) < 0.005, s.battery_resistance
    assert "BAT_HIGH_RESISTANCE" not in s.fault_codes()


@test
def bus_missing():
    bus, ups = make()
    del bus.devices[0x6B]
    s = run_for(ups, 2)
    assert not s.charger_ok and "BUS_CHARGER_MISSING" in s.fault_codes()
    del bus.devices[0x28]
    s = run_for(ups, 2)
    assert "BUS_PD_MISSING" in s.fault_codes()


@test
def state_file_and_early_cutoff():
    path = "ups_hat_test_state.json"
    bus, ups = make(state_file=path)
    bus.bq.set_status(vbus=False, pg=False, chg=0)
    bus.bq.adc.update(vbus=0, ibus=0, vbat=7200, ibat=-1500 & 0xFFFF)
    run_for(ups, 4)
    ups.save_state()                 # simulates the periodic save before power was lost
    bus2, ups2 = make(state_file=path)
    s = run_for(ups2, 2)
    assert "BAT_EARLY_CUTOFF" in s.fault_codes()
    ups2.acknowledge("BAT_EARLY_CUTOFF")
    s = run_for(ups2, 2)
    assert "BAT_EARLY_CUTOFF" not in s.fault_codes()
    import os
    os.remove(path)


@test
def clean_shutdown_is_not_early_cutoff():
    path = "ups_hat_test_state2.json"
    bus, ups = make(state_file=path)
    bus.bq.set_status(vbus=False, pg=False, chg=0)
    bus.bq.adc.update(vbus=0, ibus=0, vbat=7200, ibat=-1500 & 0xFFFF)
    run_for(ups, 4)
    ups.save_state(clean=True)
    bus2, ups2 = make(state_file=path)
    s = run_for(ups2, 2)
    assert "BAT_EARLY_CUTOFF" not in s.fault_codes()
    assert ups2.battery.soc is not None
    import os
    os.remove(path)


@test
def soc_anchors_at_charge_done():
    bus, ups = make()
    bus.bq.set_status(chg=7)
    bus.bq.adc.update(vbat=8200, ibat=0)
    s = run_for(ups, 4)
    assert abs(s.soc - 100.0) < 1e-6
    bus.bq.set_status(vbus=False, pg=False, chg=0)
    bus.bq.adc.update(vbus=0, ibus=0, vbat=7900, ibat=-2000 & 0xFFFF)
    s = run_for(ups, 3600, step=10)
    cap = ups.battery.capacity_mah
    expected = 100.0 - 2000.0 / cap * 100.0
    assert abs(s.soc - expected) < 1.0, (s.soc, expected)
    assert abs(s.time_to_empty_h - s.remaining_mah / 2000.0) < 1e-6


@test
def callbacks_fire():
    bus, ups = make()
    seen, cleared = [], []
    ups.on_fault(lambda f: seen.append(f.code))
    ups.on_clear(lambda f: cleared.append(f.code))
    bus.bq.set_status(fault1=0x04)
    run_for(ups, 2)
    bus.bq.set_status(fault1=0)
    run_for(ups, 2)
    assert seen == ["CHG_THERMAL_SHUTDOWN"] and cleared == ["CHG_THERMAL_SHUTDOWN"], (seen, cleared)


@test
def report_and_dict():
    bus, ups = make()
    s = run_for(ups, 2)
    txt = ups.report(s)
    assert "Battery" in txt and "Faults       : none" in txt
    d = s.to_dict()
    assert d["vbat"] == s.vbat and isinstance(d["faults"], list)
    import json
    json.dumps(d)


@test
def driver_settings_roundtrip():
    bus, ups = make()
    c = ups.charger
    c.min_system_voltage = 6.5
    assert abs(c.min_system_voltage - 6.5) < 1e-6
    c.input_voltage_limit = 8.0
    assert abs(c.input_voltage_limit - 8.0) < 1e-6
    c.termination_current = 0.12
    assert abs(c.termination_current - 0.12) < 1e-6
    c.recharge_offset = 0.1
    assert abs(c.recharge_offset - 0.1) < 1e-6
    c.charge_timer_h = 8
    assert c.charge_timer_h == 8
    c.thermal_regulation_c = 100
    assert c.thermal_regulation_c == 100
    assert c.cell_count == 2 and c.switching_frequency_khz == 750
    ups.set_charge_voltage(9.0)
    assert abs(c.charge_voltage - 8.4) < 1e-6, "clamped to 8.4 V"
    ups.set_charge_current(4.0)
    assert abs(c.charge_current - 3.0) < 1e-6, "clamped to 3 A"
    ups.enable_charging(False)
    assert not c.charge_enabled
    assert c.part_information()["part_number"] == 3


@test
def ts_divider_fixed_no_ntc():
    bus, ups = make()
    s = run_for(ups, 6)
    assert "BOARD_TS_FAULT" not in s.fault_codes() and not hasattr(s, "bat_temp")
    assert not (bus.bq.r[0x18] & 1)                        # library leaves TS_IGNORE alone
    bus.bq.adc.update(ts=int(85.5 / 0.0976563))           # R5 open: TS reads cold
    bus.bq.r[0x1F] = 0x08                                 # TS_COLD
    s = run_for(ups, 7)
    assert "BOARD_TS_FAULT" in s.fault_codes(), s.fault_codes()
    bus.bq.adc.update(ts=int(60.0 / 0.0976563)); bus.bq.r[0x1F] = 0
    s = run_for(ups, 3)
    assert "BOARD_TS_FAULT" not in s.fault_codes()


def main():
    failed = 0
    for t in TESTS:
        CLOCK.t = 1000.0
        try:
            t()
            print("PASS", t.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", t.__name__, repr(e))
            if sys.implementation.name != "micropython":
                import traceback
                traceback.print_exc()
    print("{} tests, {} failed".format(len(TESTS), failed))
    return failed


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
