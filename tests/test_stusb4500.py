"""ups_hat.stusb4500: USB-C PD controller driver, PDO/RDO decoding and NVM handling."""

import unittest
from unittest import mock

import helpers  # noqa: F401
from sim import FakeI2C
from ups_hat import stusb4500 as st_mod
from ups_hat.board import FACTORY_PDOS
from ups_hat.bus import BusError, DeviceNotFound, UPSError
from ups_hat.stusb4500 import PDO, STUSB4500, Contract


def pd_chip():
    bus = FakeI2C(bq=False)
    return bus, STUSB4500(bus)


class ConstructionTests(unittest.TestCase):
    def test_device_ids(self):
        for did in st_mod.DEVICE_IDS:
            with self.subTest(did=hex(did)):
                bus = FakeI2C(bq=False)
                bus.stusb.r[0x2F] = did
                self.assertEqual(STUSB4500(bus).device_id, did)

    def test_wrong_id(self):
        bus = FakeI2C(bq=False)
        bus.stusb.r[0x2F] = 0x00
        with self.assertRaises(DeviceNotFound):
            STUSB4500(bus)
        STUSB4500(bus, check=False)

    def test_missing_chip(self):
        with self.assertRaises(BusError):
            STUSB4500(FakeI2C(bq=False, pd=False))


class PdoContractTests(unittest.TestCase):
    def test_pdo_decode(self):
        p = PDO((180 << 10) | 300)
        self.assertAlmostEqual(p.voltage, 9.0)
        self.assertAlmostEqual(p.current, 3.0)
        self.assertEqual(repr(p), "PDO(9.00 V, 3.00 A)")

    def test_contract_decode(self):
        raw = (3 << 28) | (1 << 27) | (1 << 26) | (250 << 10) | 300
        k = Contract(raw)
        self.assertEqual(k.position, 3)
        self.assertAlmostEqual(k.operating_current, 2.5)
        self.assertAlmostEqual(k.max_current, 3.0)
        self.assertTrue(k.capability_mismatch and k.give_back and k.valid)
        self.assertEqual(repr(k), "Contract(source PDO 3, 2.50 A, capability mismatch)")

    def test_no_contract(self):
        k = Contract(0)
        self.assertFalse(k.valid)
        self.assertEqual(repr(k), "Contract(none)")

    def test_contract_from_chip(self):
        bus, pd = pd_chip()
        bus.stusb.set_contract(2, 3.0)
        self.assertEqual(pd.contract.position, 2)
        self.assertAlmostEqual(pd.contract.operating_current, 3.0)


class StatusTests(unittest.TestCase):
    def test_attached_sink(self):
        bus, pd = pd_chip()
        bus.stusb.set_attached(cc="1.5 A")
        s = pd.status()
        self.assertTrue(s["attached"] and s["vbus_valid"] and s["vbus_ready"])
        self.assertFalse(s["vbus_vsafe0v"])
        self.assertEqual((s["power_role"], s["data_role"]), ("sink", "UFP"))
        self.assertEqual(s["cc1"], "1.5 A")
        self.assertEqual(s["typec_state"], "Attached.SNK")
        self.assertEqual((s["pe_state"], s["pe_state_text"]), (0x18, "SNK ready"))
        self.assertTrue(pd.contract_ready)

    def test_detached_and_unknown_codes(self):
        bus, pd = pd_chip()
        bus.stusb.set_attached(attached=False, vbus_valid=False, pe_ready=False)
        bus.stusb.r[0x15] = 0x80 | 0x1F            # CC2 orientation, unknown FSM code
        bus.stusb.r[0x29] = 0x55
        bus.stusb.r[0x13] = 0x80 | 0x40 | 0x20
        s = pd.status()
        self.assertFalse(s["attached"])
        self.assertTrue(s["vbus_vsafe0v"])
        self.assertEqual(s["orientation"], "CC2")
        self.assertEqual(s["typec_state"], "0x1F")
        self.assertEqual(s["pe_state_text"], "0x55")
        self.assertTrue(s["vpu_ovp"] and s["vpu_present"] and s["vbus_discharge_fault"])
        self.assertFalse(pd.contract_ready)

    def test_status_leaves_transition_registers_alone(self):
        bus, pd = pd_chip()
        bus.stusb.r[0x0F] = 0x02
        pd.status()
        self.assertEqual(bus.stusb.r[0x0F], 0x02)

    def test_monitoring_events_read_and_clear(self):
        bus, pd = pd_chip()
        bus.stusb.r[0x0D] = 0x01
        bus.stusb.r[0x0F] = 0x02 | 0x08 | 0x10 | 0x20
        bus.stusb.r[0x12] = 0x20 | 0x80
        self.assertEqual(pd.monitoring_events(), ["ATTACH_CHANGED", "VBUS_VALID_CHANGED", "VBUS_READY_CHANGED",
                                                  "VBUS_LOW", "VBUS_HIGH", "VPU_OVP", "THERMAL_FAULT"])
        self.assertEqual(pd.monitoring_events(), [])

    def test_clear_alerts(self):
        bus, pd = pd_chip()
        bus.stusb.r[0x0B] = 0x40
        bus.stusb.r[0x0F] = 0x02
        pd.clear_alerts()
        self.assertEqual((bus.stusb.r[0x0B], bus.stusb.r[0x0F]), (0, 0))


class SinkPdoTests(unittest.TestCase):
    def test_factory_pdos(self):
        _, pd = pd_chip()
        self.assertEqual(pd.pdo_count, 3)
        got = [(round(p.voltage, 2), round(p.current, 2)) for p in pd.sink_pdos()]
        self.assertEqual(got, [tuple(map(float, p)) for p in FACTORY_PDOS])

    def test_pdo_count_clamped(self):
        bus, pd = pd_chip()
        pd.pdo_count = 0
        self.assertEqual(pd.pdo_count, 1)
        pd.pdo_count = 7
        self.assertEqual(pd.pdo_count, 3)
        self.assertEqual(len(pd.sink_pdos()), 3)
        pd.pdo_count = 2
        self.assertEqual(len(pd.sink_pdos()), 2)
        self.assertEqual(len(pd.sink_pdos(all_three=True)), 3)

    def test_set_sink_pdo(self):
        bus, pd = pd_chip()
        pd.set_sink_pdo(3, 12.0, 2.0)
        p = pd.sink_pdos()[2]
        self.assertAlmostEqual(p.voltage, 12.0)
        self.assertAlmostEqual(p.current, 2.0)

    def test_set_sink_pdo_keeps_upper_bits(self):
        bus, pd = pd_chip()
        before = pd.sink_pdos()[0].raw
        pd.set_sink_pdo(1, 20.0, 1.0)          # PDO1 is always 5 V
        after = pd.sink_pdos()[0]
        self.assertAlmostEqual(after.voltage, 5.0)
        self.assertAlmostEqual(after.current, 1.0)
        self.assertEqual(after.raw >> 20, before >> 20, "flag bits untouched")

    def test_set_sink_pdo_clamps(self):
        bus, pd = pd_chip()
        pd.set_sink_pdo(2, 30.0, 9.0)
        p = pd.sink_pdos()[1]
        self.assertAlmostEqual(p.voltage, 20.0)
        self.assertAlmostEqual(p.current, 5.0)
        pd.set_sink_pdo(2, 1.0, -1.0)
        p = pd.sink_pdos()[1]
        self.assertAlmostEqual(p.voltage, 5.0)
        self.assertAlmostEqual(p.current, 0.0)

    def test_set_sink_pdo_bad_index(self):
        _, pd = pd_chip()
        for i in (0, 4, -1):
            with self.subTest(i=i), self.assertRaises(ValueError):
                pd.set_sink_pdo(i, 9.0, 3.0)

    def test_renegotiate_sends_soft_reset(self):
        bus, pd = pd_chip()
        pd.renegotiate()
        self.assertEqual(bus.stusb.soft_resets, 1)

    def test_software_reset_pulses_reset_register(self):
        bus, pd = pd_chip()
        writes = []
        real = bus.stusb.write
        bus.stusb.write = lambda reg, data: (writes.append((reg, bytes(data))), real(reg, data))
        with mock.patch.object(st_mod, "sleep_ms") as sleep:
            pd.software_reset()
        self.assertEqual(writes, [(0x23, b"\x01"), (0x23, b"\x00")])
        sleep.assert_called_once_with(30)


class NvmTests(unittest.TestCase):
    def test_read(self):
        bus, pd = pd_chip()
        sectors = pd.read_nvm()
        self.assertEqual(len(sectors), 5)
        self.assertTrue(all(isinstance(s, bytes) and len(s) == 8 for s in sectors))
        self.assertEqual(sectors[3], bytes(bus.stusb.nvm[3]))
        self.assertEqual(bus.stusb.r[0x95], 0, "password cleared afterwards")

    def test_write_needs_confirm_and_valid_sectors(self):
        bus, pd = pd_chip()
        good = pd.read_nvm()
        with self.assertRaises(UPSError):
            pd.write_nvm(good)
        for bad in (good[:4], good[:4] + [b"\x00" * 7]):
            with self.subTest(n=len(bad)), self.assertRaises(ValueError):
                pd.write_nvm(bad, confirm=True)
        self.assertEqual(bus.stusb.nvm_writes, 0)

    def test_write_programs_all_sectors(self):
        bus, pd = pd_chip()
        new = [bytes([i] * 8) for i in range(5)]
        pd.write_nvm(new, confirm=True)
        self.assertEqual(bus.stusb.nvm_writes, 5)
        self.assertEqual(pd.read_nvm(), new)
        self.assertEqual(bus.stusb.r[0x95], 0)

    def test_timeout_raises_and_still_locks(self):
        bus, pd = pd_chip()
        real = bus.stusb.write

        def stuck(reg, data):          # the REQ bit never clears
            real(reg, data)
            if reg == 0x96:
                bus.stusb.r[0x96] |= 0x10
        bus.stusb.write = stuck
        with mock.patch.object(st_mod, "sleep_ms"):
            with self.assertRaises(UPSError):
                pd.read_nvm()
        self.assertEqual(bus.stusb.r[0x95], 0, "password cleared in finally")

    def test_decode_factory_image(self):
        _, pd = pd_chip()
        n, pdos = STUSB4500.decode_nvm_pdos(pd.read_nvm())
        self.assertEqual(n, 3)
        self.assertEqual(len(pdos), 3)
        self.assertEqual(pdos[0][0], 5.0)

    def test_encode_decode_round_trip(self):
        _, pd = pd_chip()
        base = pd.read_nvm()
        for pdos, count in ((FACTORY_PDOS, 3), (((5.0, 1.5), (12.0, 2.0), (20.0, 5.0)), 2),
                            (((5.0, 0.0), (9.0, 0.5), (15.0, 3.0)), 1)):
            with self.subTest(pdos=pdos):
                n, got = STUSB4500.decode_nvm_pdos(STUSB4500.encode_nvm_pdos(base, pdos, count))
                self.assertEqual(n, count)
                for (v, a), (gv, ga) in zip(pdos, got):
                    self.assertAlmostEqual(gv, v if v else 5.0, places=2)
                    self.assertAlmostEqual(ga, a, places=2)

    def test_encode_changes_only_pdo_bits(self):
        _, pd = pd_chip()
        base = pd.read_nvm()
        new = STUSB4500.encode_nvm_pdos(base, FACTORY_PDOS, 3)
        self.assertEqual(new[:3], base[:3], "sectors 0-2 untouched")
        self.assertEqual(new[3][0:2], base[3][0:2])
        self.assertEqual(new[3][6:], base[3][6:])
        self.assertEqual(new[4][4:], base[4][4:])

    def test_current_codes(self):
        """NVM current codes: 0 = 0 A, 1-10 = 0.5-2.75 A in 0.25 A, 11-15 = 3-5 A in 0.5 A."""
        _, pd = pd_chip()
        base = pd.read_nvm()
        for amps in (0.5, 0.75, 1.0, 2.75, 3.0, 3.5, 4.5, 5.0):
            with self.subTest(amps=amps):
                _, got = STUSB4500.decode_nvm_pdos(
                    STUSB4500.encode_nvm_pdos(base, ((5.0, amps), (9.0, amps), (15.0, amps)), 3))
                self.assertEqual([round(a, 2) for _, a in got], [amps] * 3)


if __name__ == "__main__":
    unittest.main()
