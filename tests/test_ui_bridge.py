"""Synthetic end-to-end checks for the optional UI bridge."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("screening_ui_bridge", ROOT / "ui/bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.alert = {"alert_id": "TEST-ALERT", "screened_at": "2026-06-01",
                      "customer": {"name": "Mara Ellis", "entity_type": "Individual"},
                      "account_ref": "TEST-ACCOUNT", "hit_ids": ["TEST-HIT"]}
        self.hit = {"hit_id": "TEST-HIT", "alert_id": "TEST-ALERT", "name": "Mara Ellis",
                    "entity_type": "Individual", "dobs": ["1980-04-03"],
                    "countries": ["United Kingdom"], "categories": ["PEP"], "aliases": []}
        self.record = {"record_id": "TEST-CUSTOMER", "full_name": "Mara Ellis",
                       "entity_type": "Individual", "dob": "1980-04-03",
                       "email": "mara@example.test", "residence_country": "GB",
                       "nationality": "British", "phone": "+44000000123"}
        tables = {"alerts": [self.alert], "hits": [self.hit], "customers": [self.record],
                  "accounts": [{"account_id": "TEST-ACCOUNT", "customer_id": "TEST-CUSTOMER"}],
                  "onboarding": [], "kyc_checks": [], "notes": [], "search_results": []}
        for name, rows in tables.items():
            (self.folder / (name + ".jsonl")).write_text(bridge.prediction_text(rows), encoding="utf-8")
        (self.folder / "name_variants.json").write_text('{"groups": [], "company_legal_forms": []}')

    def test_real_runner_confirms_and_cites_existing_records(self):
        result = bridge.run_screening(self.folder)
        self.assertEqual(result["counts"]["SAME_ENTITY"], 1)
        self.assertFalse(result["cleared_alert_ids"])
        prediction = result["predictions"][0]
        self.assertEqual(set(prediction), bridge.OUTPUT_FIELDS)
        self.assertEqual(prediction["customer_record_id"], "TEST-CUSTOMER")
        self.assertIn("TEST-CUSTOMER", prediction["evidence"])

    def test_conflicting_birth_date_clears(self):
        self.hit["dobs"] = ["1940-04-03"]
        (self.folder / "hits.jsonl").write_text(bridge.prediction_text([self.hit]))
        result = bridge.run_screening(self.folder)
        self.assertEqual(result["predictions"][0]["decision"], "DIFFERENT_ENTITY")
        self.assertEqual(result["cleared_alert_ids"], ["TEST-ALERT"])

    def test_one_review_keeps_whole_alert_open(self):
        second = dict(self.hit, hit_id="TEST-OTHER", dobs=[])
        self.alert["hit_ids"].append("TEST-OTHER")
        self.hit["dobs"] = ["1940"]
        (self.folder / "hits.jsonl").write_text(bridge.prediction_text([self.hit, second]))
        (self.folder / "alerts.jsonl").write_text(bridge.prediction_text([self.alert]))
        result = bridge.run_screening(self.folder)
        self.assertEqual(result["counts"]["REVIEW"], 1)
        self.assertFalse(result["cleared_alert_ids"])

    def test_inspect_uses_customer_resolution_and_original_sources(self):
        result = bridge.inspect_hit(self.folder, "TEST-HIT")
        self.assertEqual(result["persons"][0]["record_id"], "TEST-CUSTOMER")
        self.assertEqual(result["evidence_index"]["TEST-CUSTOMER"][0]["table"], "customers")
        self.assertEqual(result["hit"]["dobs"], ["1980-04-03"])

    def test_labels_are_never_predictor_input(self):
        original = bridge.run_screening(self.folder)
        (self.folder / "practice_labels.jsonl").write_text('not valid json or an input table')
        (self.folder / "gold.labels.jsonl").write_text('SAME_ENTITY is not a real record')
        again = bridge.run_screening(self.folder)
        self.assertEqual(original["fingerprint"], again["fingerprint"])
        self.assertEqual(original["predictions"], again["predictions"])

    def test_input_change_invalidates_fingerprint(self):
        first = bridge.fingerprint(self.folder)
        self.record["dob"] = "1970-04-03"
        (self.folder / "customers.jsonl").write_text(bridge.prediction_text([self.record]))
        self.assertNotEqual(first, bridge.fingerprint(self.folder))

    def test_missing_and_duplicate_predictions_are_rejected(self):
        with self.assertRaises(ValueError):
            bridge.validate_predictions(self.folder, [])
        prediction = bridge.run_screening(self.folder)["predictions"][0]
        with self.assertRaises(ValueError):
            bridge.validate_predictions(self.folder, [prediction, prediction])

    def test_evaluation_uses_the_official_validator(self):
        result = bridge.run_screening(self.folder)
        labels = self.folder / "answers.jsonl"
        labels.write_text(bridge.prediction_text([{
            "hit_id": "TEST-HIT", "decision": "SAME_ENTITY",
            "reason_codes": ["NAME_DOB_LOCATION_MATCH"],
            "customer_record_ids": ["TEST-CUSTOMER"],
        }]))
        report = bridge.evaluate(self.folder, result["predictions"], labels)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["score"], 100.0)
        self.assertEqual(report["unsafe_clearances"], 0)


if __name__ == "__main__":
    unittest.main()
