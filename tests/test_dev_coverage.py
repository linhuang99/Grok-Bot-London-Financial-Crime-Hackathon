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
from link import linked_records, resolve  # noqa: E402
from customer import person  # noqa: E402
import re  # noqa: E402
import json  # noqa: E402

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

    def resolve_all(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return {a["alert_id"]: resolve(a, self.data) for a in self.data["alerts"]}

    def test_every_linked_alert_resolves_to_exactly_one_person(self):
        people = self.resolve_all()
        linked = [a for a in self.data["alerts"] if linked_records(a, self.data)]
        self.assertEqual(len(linked), 294)
        self.assertEqual([a["alert_id"] for a in linked if len(people[a["alert_id"]]) != 1], [])

    def test_every_joint_account_alert_picks_one_holder(self):
        people = self.resolve_all()
        joint = [a for a in self.data["alerts"] if len(linked_records(a, self.data)) > 1]
        self.assertEqual(len(joint), 58)
        self.assertEqual([a["alert_id"] for a in joint if len(people[a["alert_id"]]) != 1], [])

    def test_scorecard_linked_practice_labels_resolve_to_an_accepted_record(self):
        # Practice labels are read by this test only, never by the system.
        people = self.resolve_all()
        alerts = {a["alert_id"]: a for a in self.data["alerts"]}
        with open(os.path.join(DEV, "practice_labels.jsonl"), encoding="utf-8") as f:
            labels = [json.loads(line) for line in f]
        linked = [x for x in labels if linked_records(alerts[x["alert_id"]], self.data)]
        wrong = [x["hit_id"] for x in linked
                 if not any(r in x["customer_record_ids"] for person in people[x["alert_id"]] for r in person)
                 or len(people[x["alert_id"]]) != 1]
        self.assertEqual(len(linked), 38)
        self.assertEqual(wrong, [])

    def labels(self):
        with open(os.path.join(DEV, "practice_labels.jsonl"), encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_person_builds_for_every_resolved_alert(self):
        people = [p for ps in self.resolve_all().values() for p in ps]
        start = time.perf_counter()
        persons = [person(p, self.data) for p in people]
        self.assertTrue(all(self.resolve_all().values()))  # every alert finds at least one customer
        self.assertEqual(len(persons), 512)
        self.assertLess(time.perf_counter() - start, 5)
        self.assertTrue(all(p["legal_name"] for p in persons))

    def test_scorecard_latest_approved_check_matches_every_label_path(self):
        # Practice labels are read by this test only, never by the system.
        people, checked = self.resolve_all(), 0
        for label in self.labels():
            for step in label["path"]:
                cited = re.search(r"latest approved check (KYC-[0-9A-F]+)", step)
                if not cited:
                    continue
                start = re.match(r"(CUS-\d+)", step)
                candidates = [[start.group(1)]] if start else people[label["alert_id"]]
                sources = [(person(ids, self.data)["verified_name"] or {}).get("source") for ids in candidates]
                self.assertIn(cited.group(1), sources, label["hit_id"])
                checked += 1
        self.assertEqual(checked, 32)

    def test_kyc_evidence_of_linked_labels_is_among_our_sources(self):
        people, missing = self.resolve_all(), []
        alerts = {a["alert_id"]: a for a in self.data["alerts"]}
        for label in self.labels():
            if not linked_records(alerts[label["alert_id"]], self.data):
                continue
            p = person(people[label["alert_id"]][0], self.data)
            sources = {f["source"] for f in [p["verified_name"], p["dob"]] + p["countries"] if f}
            missing += [(label["hit_id"], e) for e in label["evidence"] if e.startswith("KYC-") and e not in sources]
        self.assertEqual(missing, [])

    def test_latest_check_not_approved_still_uses_the_approved_one(self):
        cases = 0
        for record in self.data["customers"]:
            checks = []
            for account in self.data["accounts_by_customer"].get(record["record_id"], []):
                applicant = self.data["applicant_by_account_customer"].get((account["account_id"], record["record_id"]))
                checks += self.data["kyc_by_applicant"].get(applicant, [])
            approved = [c for c in checks if c["result"] == "approved"]
            if approved and max(checks, key=lambda c: c["checked_at"])["result"] != "approved":
                cases += 1
                self.assertEqual(person([record["record_id"]], self.data)["verified_name"]["source"],
                                 max(approved, key=lambda c: c["checked_at"])["check_id"])
        self.assertEqual(cases, 1684)

    def test_kyc_notes_read_into_checks(self):
        from notes import is_kyc_note, kyc_check
        email_owner = {c["email"]: c for c in self.data["customers"]}
        checks = [(kyc_check(n), email_owner[n["requester_email"]]) for n in self.data["notes"] if is_kyc_note(n)]
        self.assertEqual(len(checks), 22575)
        # The 38 without a name carry placeholders ("N/A", "0000"): no usable name is correct.
        self.assertEqual(sum(c["verified_name"] is None for c, _ in checks), 38)
        dobs = [(parse_date(c["verified_dob"]), parse_date(r["dob"])) for c, r in checks]
        self.assertEqual(sum(a is None for a, _ in dobs), 0)
        self.assertEqual(sum(a != b for a, b in dobs if b), 18)  # verified dates that overrule a recorded one

    def test_note_evidence_of_linked_labels_is_among_our_sources(self):
        people, missing = self.resolve_all(), []
        alerts = {a["alert_id"]: a for a in self.data["alerts"]}
        for label in self.labels():
            if not linked_records(alerts[label["alert_id"]], self.data):
                continue
            p = person(people[label["alert_id"]][0], self.data)
            sources = {f["source"] for f in [p["verified_name"], p["dob"]] + p["countries"] if f}
            missing += [(label["hit_id"], e) for e in label["evidence"] if e.startswith("NOTE-") and e not in sources]
        self.assertEqual(missing, [])

    def test_scorecard_unlinked_practice_labels_find_their_customer(self):
        people, wrong = self.resolve_all(), []
        alerts = {a["alert_id"]: a for a in self.data["alerts"]}
        unlinked = [x for x in self.labels() if not linked_records(alerts[x["alert_id"]], self.data)]
        for label in unlinked:
            found = [r for p in people[label["alert_id"]] for r in p]
            if label["customer_record_ids"] == ["AMBIGUOUS"]:
                ok = len(people[label["alert_id"]]) > 1
            else:
                ok = bool(found) and set(found) <= set(label["customer_record_ids"])
            if not ok:
                wrong.append(label["hit_id"])
        self.assertEqual(len(unlinked), 12)
        self.assertEqual(wrong, [])


if __name__ == "__main__":
    unittest.main()
