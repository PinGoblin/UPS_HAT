"""ups_hat.faults: the fault catalogue and the Fault class."""

import json
import os
import re
import unittest

import helpers
from ups_hat import faults
from ups_hat.faults import CATALOGUE, CRITICAL, INFO, SEVERITY_NAMES, WARNING, Fault

SOURCES = {"charger", "pd", "bus", "inferred", "pi"}


def _source(name):
    with open(os.path.join(helpers.ROOT, "ups_hat", name)) as f:
        return f.read()


class CatalogueTests(unittest.TestCase):
    def test_entries_are_well_formed(self):
        for code, entry in CATALOGUE.items():
            with self.subTest(code=code):
                self.assertRegex(code, r"^[A-Z][A-Z0-9_]+$")
                self.assertEqual(len(entry), 4)
                sev, src, msg, adv = entry
                self.assertIn(sev, (INFO, WARNING, CRITICAL))
                self.assertIn(src, SOURCES)
                self.assertTrue(msg and msg.strip() == msg, "message must be non-empty and trimmed")
                self.assertTrue(msg.endswith("."), "message should be a sentence")
                self.assertIsInstance(adv, str)

    def test_critical_and_warning_faults_give_advice(self):
        for code, (sev, _, _, adv) in CATALOGUE.items():
            if sev >= WARNING:
                with self.subTest(code=code):
                    self.assertTrue(adv, "warnings and critical faults need advice")

    def test_prefix_matches_source(self):
        prefixes = {"BUS_": {"bus"}, "CHG_": {"charger"}, "PD_": {"pd"}, "PI_": {"pi", "inferred"}}
        for code, (_, src, _, _) in CATALOGUE.items():
            for prefix, allowed in prefixes.items():
                if code.startswith(prefix):
                    with self.subTest(code=code):
                        self.assertIn(src, allowed)

    def test_every_code_is_raised_somewhere(self):
        board = _source("board.py")
        for code in CATALOGUE:
            with self.subTest(code=code):
                self.assertIn('"%s"' % code, board, "catalogue entry never raised by board.py")

    def test_every_raised_code_is_catalogued(self):
        board = _source("board.py")
        raised = set(re.findall(r'"((?:BUS|CHG|PD|BAT|ADAPTER|CABLE|OUTPUT|BOARD|PI)_[A-Z0-9_]+)"', board))
        missing = raised - set(CATALOGUE)
        self.assertEqual(missing, set())

    def test_severity_names(self):
        self.assertEqual(SEVERITY_NAMES, ("info", "warning", "critical"))

    def test_charge_blocked_wording(self):
        adv = CATALOGUE["BAT_CHARGE_BLOCKED"][3]
        self.assertIn("protection", adv)
        self.assertIn("4.25 V", adv)

    def test_text_follows_the_documentation_style(self):
        for code, (_, _, msg, adv) in CATALOGUE.items():
            for text in (msg, adv):
                with self.subTest(code=code, text=text):
                    self.assertIsNone(re.search(r": [a-z]", text), "capitalise the word after a colon")
                    self.assertNotIn("I2C", text, "write I²C")
                    self.assertNotIn(";", text, "use two sentences, or a colon")
                    self.assertIsNone(re.search(r"\babout \d", text), "give a definite figure")


class FaultTests(unittest.TestCase):
    def test_from_catalogue(self):
        f = Fault("BAT_CRITICAL", {"soc": 4.2}, since=12.0)
        self.assertEqual(f.severity, CRITICAL)
        self.assertEqual(f.severity_name, "critical")
        self.assertEqual(f.source, "inferred")
        self.assertEqual(f.message, CATALOGUE["BAT_CRITICAL"][2])
        self.assertEqual(f.since, 12.0)
        self.assertFalse(f.transient)

    def test_unknown_code_defaults_to_inferred_warning(self):
        f = Fault("SOMETHING_NEW")
        self.assertEqual((f.severity, f.source, f.message, f.advice), (WARNING, "inferred", "SOMETHING_NEW", ""))
        self.assertEqual(f.data, {})

    def test_data_is_not_shared_between_faults(self):
        a, b = Fault("BAT_LOW"), Fault("BAT_LOW")
        a.data["x"] = 1
        self.assertEqual(b.data, {})

    def test_to_dict_is_json_serialisable(self):
        f = Fault("CHG_IBUS_OCP", {"ibus": 3.2}, transient=True, since=5.0)
        d = f.to_dict()
        self.assertEqual(d["severity"], "warning")
        self.assertTrue(d["transient"])
        self.assertEqual(json.loads(json.dumps(d)), d)

    def test_repr(self):
        self.assertEqual(repr(Fault("BAT_LOW")), "Fault(BAT_LOW, warning)")
        self.assertEqual(repr(Fault("CHG_IBUS_OCP", transient=True)), "Fault(CHG_IBUS_OCP, warning, transient)")

    def test_str_formats_data_sorted_and_rounded(self):
        f = Fault("BAT_HIGH_RESISTANCE", {"ohm": 0.41234, "baseline": None})
        self.assertEqual(str(f), "[WARNING] BAT_HIGH_RESISTANCE: Battery path resistance is high. "
                                 "(baseline=None, ohm=0.412)")
        self.assertEqual(str(Fault("BAT_ABSENT")), "[CRITICAL] BAT_ABSENT: No battery detected.")

    def test_fmt(self):
        self.assertEqual(faults._fmt(1234.5678), "1.23e+03")
        self.assertEqual(faults._fmt(7), "7")
        self.assertEqual(faults._fmt("x"), "x")


class FaultsPageTests(unittest.TestCase):
    """docs/api/faults.md must be regenerated whenever the catalogue changes."""

    def test_page_is_up_to_date(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_faults_md",
                                                      os.path.join(helpers.ROOT, "tools", "gen_faults_md.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with open(mod.PATH) as f:
            self.assertEqual(f.read(), mod.render(), "run: python3 tools/gen_faults_md.py")
        for code in CATALOGUE:
            self.assertIn("`%s`" % code, mod.render())


if __name__ == "__main__":
    unittest.main()
