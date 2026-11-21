"""Coverage and regression checks on the real dev data (skipped when dev/ is absent).

dev/ is never committed, so these only run on a machine with the data room copied in.
"""
import contextlib
import io
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from common import country_at_end, country_name, parse_date  # noqa: E402
from data import find_search_results, id_key, load, text_key  # noqa: E402

DEV = os.path.join(ROOT, "dev")


@unittest.skipUnless(os.path.isdir(DEV), "dev/ data not present")
class DevData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start = time.perf_counter()
        with contextlib.redirect_stderr(io.StringIO()):
            cls.data = load(DEV)
        cls.seconds = time.perf_counter() - start

    def test_loads_cleanly_and_quickly(self):
        self.assertEqual(self.data["warnings"], [])
        self.assertLess(self.seconds, 10)

    def test_row_counts(self):
        counts = {name: len(self.data[name]) for name in
                  ("alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks", "notes", "search_results")}
        self.assertEqual(counts, {"alerts": 440, "hits": 819, "customers": 72265, "accounts": 86659,
                                  "onboarding": 72265, "kyc_checks": 54488, "notes": 31895, "search_results": 16882})

    def test_every_alert_link_resolves(self):
        found = {"account": 0, "login": 0, "email": 0}
        for alert in self.data["alerts"]:
            if id_key(alert.get("account_ref")):
                found["account"] += bool(self.data["accounts_by_id"].get(id_key(alert["account_ref"])))
            if text_key(alert.get("login_handle")):
                found["login"] += bool(self.data["accounts_by_login"].get(text_key(alert["login_handle"])))
            if text_key(alert.get("email")):
                found["email"] += bool(self.data["customers_by_email"].get(text_key(alert["email"])))
        self.assertEqual(found, {"account": 170, "login": 70, "email": 54})

    def test_joint_accounts(self):
        joint = [k for k, rows in self.data["accounts_by_id"].items() if len(rows) > 1]
        self.assertEqual(len(joint), 52)

    def test_every_individual_hit_finds_its_search_results(self):
        individuals = [h for h in self.data["hits"] if h.get("entity_type") == "Individual"]
        with_results = sum(bool(find_search_results(self.data, h["name"])) for h in individuals)
        self.assertEqual(with_results, len(individuals))  # 702 in dev; company hits have none

    def test_every_structured_date_parses(self):
        values = [c["dob"] for c in self.data["customers"]]
        values += [k[f] for k in self.data["kyc_checks"] for f in ("verified_dob", "checked_at")]
        values += [a["customer"]["dob"] for a in self.data["alerts"]]
        values += [d for h in self.data["hits"] for d in h["dobs"] + [h["deceased_date"]]]
        self.assertEqual(sorted({v for v in values if v and parse_date(v) is None}), [])

    def test_every_customer_side_country_is_recognised(self):
        values = [c[f] for c in self.data["customers"] for f in ("residence_country", "nationality")]
        values += [k["document_country"] for k in self.data["kyc_checks"]]
        values += [a["customer"]["country"] for a in self.data["alerts"]]
        self.assertEqual(sorted({v for v in values if v and country_name(v) is None}), [])

    def test_every_hit_country_is_recognised_apart_from_regions(self):
        unknown = set()
        for h in self.data["hits"]:
            for field in ("countries", "nationality", "citizenship", "addresses", "place_of_birth"):
                value = h[field]
                for item in value if isinstance(value, list) else [value] if value else []:
                    if country_at_end(item) is None:
                        unknown.add(item)
        self.assertEqual(sorted(u for u in unknown if "International" not in u and "Europe" not in u), [])


if __name__ == "__main__":
    unittest.main()
