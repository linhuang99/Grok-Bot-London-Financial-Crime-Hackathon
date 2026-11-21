"""Unit tests for system/customer.py on small invented data folders."""
import contextlib
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from data import load  # noqa: E402
from customer import person  # noqa: E402


def record(record_id="CUS-000001", name="Maria Lopez", **fields):
    row = {"record_id": record_id, "entity_type": "Individual", "full_name": name, "preferred_name": None,
           "login_name": None, "dob": "14/03/1985", "nationality": "Spanish", "residence_country": "ES",
           "email": record_id.lower() + "@mail.example"}
    row.update(fields)
    return row


def check(check_id, result="approved", checked_at="2024-01-10", applicant="APP-000001", **fields):
    row = {"check_id": check_id, "applicant_id": applicant, "verified_name": "MARIA ELENA LOPEZ",
           "verified_dob": "1985-03-14", "document_type": "passport", "document_number": "P1234567",
           "document_country": "Spain", "result": result, "checked_at": checked_at}
    row.update(fields)
    return row


class ProfileTest(unittest.TestCase):
    def data(self, customers, checks=(), accounts=None, onboarding=None):
        if accounts is None:
            accounts = [{"account_id": "ACC-%06d" % i, "customer_id": c["record_id"]} for i, c in enumerate(customers, 1)]
        if onboarding is None:
            onboarding = [{"account_id": a["account_id"], "customer_id": a["customer_id"],
                           "kyc_applicant_id": "APP-%06d" % i} for i, a in enumerate(accounts, 1)]
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path)
        tables = {"alerts": [], "hits": [], "customers": customers, "accounts": accounts,
                  "onboarding": onboarding, "kyc_checks": list(checks)}
        for name, rows in tables.items():
            with open(os.path.join(path, name + ".jsonl"), "w", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        with contextlib.redirect_stderr(io.StringIO()):
            return load(path)


class VerifiedBeatsDeclared(ProfileTest):
    def test_no_check_uses_declared_record_facts(self):
        p = person(["CUS-000001"], self.data([record()]))
        self.assertIsNone(p["verified_name"])
        self.assertEqual(p["legal_name"], {"value": "Maria Lopez", "source": "CUS-000001"})
        self.assertEqual(p["dob"], {"value": (1985, 3, 14), "source": "CUS-000001"})
        self.assertEqual(p["record_id"], "CUS-000001")
        self.assertEqual(p["entity_type"], "Individual")

    def test_approved_check_gives_verified_name_and_dob(self):
        p = person(["CUS-000001"], self.data([record()], [check("KYC-000001")]))
        self.assertEqual(p["verified_name"], {"value": "MARIA ELENA LOPEZ", "source": "KYC-000001"})
        self.assertEqual(p["legal_name"], p["verified_name"])
        self.assertEqual(p["dob"], {"value": (1985, 3, 14), "source": "KYC-000001"})

    def test_newer_rejected_or_expired_check_does_not_hide_an_older_approved_one(self):
        for bad in ("rejected", "expired"):
            with self.subTest(bad=bad):
                p = person(["CUS-000001"], self.data([record()], [
                    check("KYC-000001", checked_at="2022-05-01"),
                    check("KYC-000002", result=bad, checked_at="2025-05-01", verified_name="SOMEONE ELSE")]))
                self.assertEqual(p["verified_name"]["source"], "KYC-000001")

    def test_only_rejected_or_expired_checks_count_as_no_check(self):
        p = person(["CUS-000001"], self.data([record()], [check("KYC-000001", result="rejected"),
                                                          check("KYC-000002", result="expired")]))
        self.assertIsNone(p["verified_name"])
        self.assertEqual(p["dob"]["source"], "CUS-000001")
        self.assertEqual({c["source"] for c in p["countries"]}, {"CUS-000001"})

    def test_newest_approved_check_wins_and_same_day_ties_are_fixed(self):
        older, newer = check("KYC-000001", checked_at="2021-01-01"), check("KYC-000002", checked_at="2024-06-30",
                                                                          verified_name="MARIA LOPEZ GARCIA")
        self.assertEqual(person(["CUS-000001"], self.data([record()], [newer, older]))["verified_name"]["source"], "KYC-000002")
        a, b = check("KYC-00000A", checked_at="2024-06-30"), check("KYC-00000B", checked_at="2024-06-30")
        first = person(["CUS-000001"], self.data([record()], [a, b]))["verified_name"]["source"]
        second = person(["CUS-000001"], self.data([record()], [b, a]))["verified_name"]["source"]
        self.assertEqual(first, second)

    def test_unreadable_check_date_counts_as_oldest(self):
        p = person(["CUS-000001"], self.data([record()], [check("KYC-000001", checked_at="soon"),
                                                          check("KYC-000002", checked_at="2020-01-01")]))
        self.assertEqual(p["verified_name"]["source"], "KYC-000002")

    def test_check_without_dob_falls_back_to_the_declared_dob(self):
        p = person(["CUS-000001"], self.data([record()], [check("KYC-000001", verified_dob=None)]))
        self.assertEqual(p["dob"], {"value": (1985, 3, 14), "source": "CUS-000001"})
        self.assertEqual(p["verified_name"]["source"], "KYC-000001")

    def test_verified_dob_overrides_a_different_declared_dob(self):
        p = person(["CUS-000001"], self.data([record(dob="1990-01-01")], [check("KYC-000001")]))
        self.assertEqual(p["dob"], {"value": (1985, 3, 14), "source": "KYC-000001"})

    def test_unreadable_dates_everywhere_leave_dob_unknown(self):
        p = person(["CUS-000001"], self.data([record(dob="unknown")], [check("KYC-000001", verified_dob="n/a")]))
        self.assertIsNone(p["dob"])

    def test_a_completely_different_verified_name_becomes_the_legal_name(self):
        p = person(["CUS-000001"], self.data([record(name="Mohammed Wahid")],
                                             [check("KYC-000001", verified_name="Emily Wahid")]))
        self.assertEqual(p["legal_name"], {"value": "Emily Wahid", "source": "KYC-000001"})
        self.assertIn({"value": "Mohammed Wahid", "source": "CUS-000001"}, p["names"])
        self.assertEqual(p["names"][0], p["legal_name"])

    def test_names_have_no_repeats_ignoring_case(self):
        p = person(["CUS-000001"], self.data([record(name="Maria Lopez", preferred_name="MARIA LOPEZ")],
                                             [check("KYC-000001", verified_name="María López")]))
        self.assertEqual([n["value"] for n in p["names"]], ["María López"])


class Countries(ProfileTest):
    def test_codes_nationalities_and_documents_meet_with_every_source(self):
        p = person(["CUS-000001"], self.data([record(residence_country="ES", nationality="Spanish")],
                                             [check("KYC-000001", document_country="Spain")]))
        self.assertEqual(p["countries"], [{"value": "Spain", "source": "CUS-000001"},
                                          {"value": "Spain", "source": "KYC-000001"}])
        self.assertEqual(p["unreadable_countries"], [])

    def test_every_approved_documents_country_counts_but_not_rejected_ones(self):
        p = person(["CUS-000001"], self.data([record()], [
            check("KYC-000001", document_country="Portugal", checked_at="2020-01-01"),
            check("KYC-000002", document_country="Spain", checked_at="2024-01-01"),
            check("KYC-000003", result="rejected", document_country="Brazil")]))
        self.assertEqual({c["value"] for c in p["countries"]}, {"Spain", "Portugal"})

    def test_unreadable_values_are_flagged_never_counted(self):
        p = person(["CUS-000001"], self.data([record(residence_country="NA", nationality="Atlantean")]))
        self.assertEqual(p["countries"], [])
        self.assertEqual(p["unreadable_countries"], [{"value": "Atlantean", "source": "CUS-000001"},
                                                     {"value": "NA", "source": "CUS-000001"}])

    def test_blank_values_are_simply_missing(self):
        p = person(["CUS-000001"], self.data([record(residence_country="", nationality=None)]))
        self.assertEqual((p["countries"], p["unreadable_countries"]), ([], []))


class Shapes(ProfileTest):
    def test_company_uses_its_registry_extract(self):
        company = record(name="Brightwater Trading Ltd", entity_type="Company", dob="05/05/2001", nationality=None)
        extract = check("KYC-000001", verified_name="Brightwater Trading Ltd", verified_dob="2001-05-05",
                        document_type="registry extract", document_number=None, document_country="Spain")
        p = person(["CUS-000001"], self.data([company], [extract]))
        self.assertEqual(p["entity_type"], "Company")
        self.assertEqual(p["legal_name"]["value"], "Brightwater Trading Ltd")
        self.assertEqual(p["dob"], {"value": (2001, 5, 5), "source": "KYC-000001"})

    def test_check_found_through_the_one_account_that_has_onboarding(self):
        accounts = [{"account_id": "ACC-000001", "customer_id": "CUS-000001"},
                    {"account_id": "ACC-000002", "customer_id": "CUS-000001"}]
        onboarding = [{"account_id": "ACC-000002", "customer_id": "CUS-000001", "kyc_applicant_id": "APP-000009"}]
        p = person(["CUS-000001"], self.data([record()], [check("KYC-000001", applicant="APP-000009")],
                                             accounts, onboarding))
        self.assertEqual(p["verified_name"]["source"], "KYC-000001")

    def test_several_records_of_one_person_combine(self):
        records = [record("CUS-000002", residence_country="GB", nationality="British"), record("CUS-000001")]
        checks = [check("KYC-000001", applicant="APP-000001", checked_at="2020-01-01"),
                  check("KYC-000002", applicant="APP-000002", checked_at="2024-01-01", verified_name="MARIA LOPEZ")]
        p = person(["CUS-000002", "CUS-000001"], self.data(records, checks))
        self.assertEqual(p["record_id"], "CUS-000002")
        self.assertEqual(p["record_ids"], ["CUS-000002", "CUS-000001"])
        self.assertEqual({c["value"] for c in p["countries"]}, {"United Kingdom", "Spain"})
        self.assertEqual(p["verified_name"]["source"], "KYC-000002")

    def test_unknown_record_ids_are_an_error(self):
        with self.assertRaises(ValueError):
            person(["CUS-999999"], self.data([record()]))

    def test_input_is_not_changed_and_output_is_stable(self):
        data = self.data([record()], [check("KYC-000001")])
        before = copy.deepcopy(data)
        self.assertEqual(person(["CUS-000001"], data), person(["CUS-000001"], data))
        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
