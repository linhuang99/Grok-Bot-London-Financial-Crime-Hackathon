"""Unit tests for system/data.py on small invented data folders."""
import ast
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM = os.path.join(ROOT, "system")
sys.path.insert(0, SYSTEM)

from data import DataError, find_search_results, id_key, load, search_keys, text_key  # noqa: E402

ALERT = {"alert_id": "A-000001", "customer": {"name": "Ann Lee"}, "account_ref": "ACC-000001",
         "login_handle": None, "email": None, "hit_ids": ["H-000001"]}
HIT = {"hit_id": "H-000001", "alert_id": "A-000001", "name": "Ann Lee"}
CUSTOMER = {"record_id": "CUS-000001", "full_name": "Ann Lee", "email": "ann.lee@mail.example", "phone": "+44 1"}


class Folder:
    """A temporary data folder; each table is a list of rows or of raw text lines."""

    def __init__(self, **tables):
        self.path = tempfile.mkdtemp()
        tables.setdefault("alerts", [ALERT])
        tables.setdefault("hits", [HIT])
        for name, rows in tables.items():
            if rows is None:
                continue
            with open(os.path.join(self.path, name + ".jsonl"), "w", encoding="utf-8") as f:
                for row in rows:
                    f.write((row if isinstance(row, str) else json.dumps(row, ensure_ascii=False)) + "\n")

    def load(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return load(self.path)

    def write_text(self, filename, text):
        with open(os.path.join(self.path, filename), "w", encoding="utf-8") as f:
            f.write(text)

    def cleanup(self):
        shutil.rmtree(self.path)


class FolderTest(unittest.TestCase):
    def folder(self, **tables):
        folder = Folder(**tables)
        self.addCleanup(folder.cleanup)
        return folder


class LoadsMinimalFolder(FolderTest):
    def test_tables_and_indexes_are_filled(self):
        folder = self.folder(customers=[CUSTOMER],
                           accounts=[{"account_id": "ACC-000001", "customer_id": "CUS-000001", "login_handle": "annlee1"}],
                           onboarding=[{"account_id": "ACC-000001", "customer_id": "CUS-000001", "kyc_applicant_id": "APP-000001"}],
                           kyc_checks=[{"check_id": "KYC-000001", "applicant_id": "APP-000001", "result": "approved"}],
                           notes=[{"note_id": "NOTE-000001", "requester_email": "ann.lee@mail.example", "text": "Hello."}],
                           search_results=[{"result_id": "SR-000001", "query": "ann lee"}])
        folder.write_text("name_variants.json", json.dumps({"groups": [], "company_legal_forms": []}))
        data = folder.load()
        self.assertEqual([a["alert_id"] for a in data["alerts"]], ["A-000001"])
        self.assertIs(data["hits_by_id"]["H-000001"], data["hits"][0])
        self.assertEqual(data["customers_by_id"]["CUS-000001"]["full_name"], "Ann Lee")
        self.assertEqual(len(data["customers_by_email"]["ann.lee@mail.example"]), 1)
        self.assertEqual(data["accounts_by_login"]["annlee1"][0]["account_id"], "ACC-000001")
        self.assertEqual(data["applicant_by_account_customer"][("ACC-000001", "CUS-000001")], "APP-000001")
        self.assertEqual(data["kyc_by_applicant"]["APP-000001"][0]["check_id"], "KYC-000001")
        self.assertEqual(data["notes_by_email"]["ann.lee@mail.example"][0]["note_id"], "NOTE-000001")
        self.assertEqual(data["search_by_query"]["ann lee"][0]["result_id"], "SR-000001")
        self.assertEqual(data["warnings"], [])

    def test_loading_twice_gives_identical_results(self):
        folder = self.folder(customers=[CUSTOMER])
        self.assertEqual(folder.load(), folder.load())


class MissingFiles(FolderTest):
    def test_folder_without_practice_labels_or_policy_loads_without_warnings(self):
        # The unseen folder has no practice_labels.jsonl; the system must never need it.
        folder = self.folder(customers=[], accounts=[], onboarding=[], kyc_checks=[], notes=[], search_results=[])
        folder.write_text("name_variants.json", json.dumps({"groups": [], "company_legal_forms": []}))
        self.assertEqual(folder.load()["warnings"], [])

    def test_missing_optional_file_gives_empty_table_and_warning(self):
        data = self.folder(customers=[CUSTOMER]).load()
        self.assertEqual(data["notes"], [])
        self.assertEqual(data["notes_by_email"], {})
        self.assertTrue(any("notes.jsonl is missing" in w for w in data["warnings"]))

    def test_missing_required_file_stops_with_a_clear_error(self):
        folder = self.folder(alerts=None)  # no alerts.jsonl written
        with self.assertRaisesRegex(DataError, "alerts.jsonl"):
            folder.load()

    def test_warnings_are_printed_to_stderr(self):
        folder = self.folder()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            load(folder.path)
        self.assertIn("customers.jsonl is missing", stderr.getvalue())


class DamagedInput(FolderTest):
    def test_blank_lines_are_ignored(self):
        data = self.folder(customers=["", json.dumps(CUSTOMER), "   "]).load()
        self.assertEqual(len(data["customers"]), 1)
        self.assertFalse(any("customers" in w for w in data["warnings"]))

    def test_damaged_line_is_skipped_with_file_and_line_and_neighbours_survive(self):
        other = dict(CUSTOMER, record_id="CUS-000002")
        data = self.folder(customers=[json.dumps(CUSTOMER), '{"record_id": "CUS-00', json.dumps(other)]).load()
        self.assertEqual([c["record_id"] for c in data["customers"]], ["CUS-000001", "CUS-000002"])
        self.assertIn("customers.jsonl line 2 is not valid JSON; skipped", data["warnings"])

    def test_line_that_is_not_an_object_is_skipped(self):
        data = self.folder(customers=["[1, 2]", json.dumps(CUSTOMER)]).load()
        self.assertEqual(len(data["customers"]), 1)
        self.assertIn("customers.jsonl line 1 is not a JSON object; skipped", data["warnings"])

    def test_byte_order_mark_and_accents_are_read_correctly(self):
        folder = self.folder()
        row = dict(CUSTOMER, full_name="Zoë Müller-Łukasz")
        with open(os.path.join(folder.path, "customers.jsonl"), "w", encoding="utf-8-sig") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        data = folder.load()
        self.assertEqual(data["customers"][0]["full_name"], "Zoë Müller-Łukasz")
        self.assertIn("CUS-000001", data["customers_by_id"])

    def test_repeated_id_keeps_the_first_row_and_warns(self):
        data = self.folder(customers=[CUSTOMER, dict(CUSTOMER, full_name="Someone Else")]).load()
        self.assertEqual(data["customers_by_id"]["CUS-000001"]["full_name"], "Ann Lee")
        self.assertEqual(len(data["customers"]), 1)
        self.assertIn("customers.jsonl repeats record_id CUS-000001; kept the first", data["warnings"])

    def test_row_without_its_id_is_skipped(self):
        data = self.folder(customers=[{"full_name": "No Id"}, CUSTOMER]).load()
        self.assertEqual(len(data["customers"]), 1)
        self.assertIn("customers.jsonl has a row without record_id; skipped", data["warnings"])

    def test_missing_or_broken_name_variants_give_empty_variants(self):
        folder = self.folder()
        self.assertEqual(folder.load()["name_variants"], {"groups": [], "company_legal_forms": []})
        folder.write_text("name_variants.json", "{not json")
        data = folder.load()
        self.assertEqual(data["name_variants"], {"groups": [], "company_legal_forms": []})
        self.assertTrue(any("name_variants.json is not valid JSON" in w for w in data["warnings"]))

    def test_name_variants_keep_groups_and_legal_forms(self):
        folder = self.folder()
        folder.write_text("name_variants.json", json.dumps(
            {"description": "x", "groups": [["jon", "john"]], "company_legal_forms": ["ltd"]}))
        self.assertEqual(folder.load()["name_variants"], {"groups": [["jon", "john"]], "company_legal_forms": ["ltd"]})


class Links(FolderTest):
    def test_joint_account_keeps_both_holders_in_file_order(self):
        data = self.folder(accounts=[{"account_id": "ACC-000009", "customer_id": "CUS-000002"},
                                     {"account_id": "ACC-000009", "customer_id": "CUS-000001"}]).load()
        self.assertEqual([a["customer_id"] for a in data["accounts_by_id"]["ACC-000009"]], ["CUS-000002", "CUS-000001"])

    def test_customer_with_two_accounts_has_both(self):
        data = self.folder(accounts=[{"account_id": "ACC-000001", "customer_id": "CUS-000001"},
                                     {"account_id": "ACC-000002", "customer_id": "CUS-000001"}]).load()
        self.assertEqual(len(data["accounts_by_customer"]["CUS-000001"]), 2)

    def test_email_and_login_lookups_ignore_case_and_spaces_but_records_keep_originals(self):
        data = self.folder(customers=[dict(CUSTOMER, email=" Ann.Lee@Mail.Example ")],
                           accounts=[{"account_id": "ACC-000001", "customer_id": "CUS-000001", "login_handle": "AnnLee1"}]).load()
        self.assertEqual(data["customers_by_email"][text_key(" ann.lee@mail.example")][0]["email"], " Ann.Lee@Mail.Example ")
        self.assertIn(text_key("ANNLEE1 "), data["accounts_by_login"])

    def test_blank_keys_mean_no_link(self):
        for blank in [None, "", "   ", 7]:
            with self.subTest(blank=blank):
                self.assertIsNone(id_key(blank))
                self.assertIsNone(text_key(blank))
        data = self.folder(customers=[dict(CUSTOMER, email="")]).load()
        self.assertEqual(data["customers_by_email"], {})

    def test_account_without_onboarding_has_no_applicant(self):
        data = self.folder(accounts=[{"account_id": "ACC-000001", "customer_id": "CUS-000001"}], onboarding=[]).load()
        self.assertNotIn(("ACC-000001", "CUS-000001"), data["applicant_by_account_customer"])

    def test_applicant_with_two_checks_keeps_both_in_file_order(self):
        data = self.folder(kyc_checks=[{"check_id": "KYC-000002", "applicant_id": "APP-000001", "result": "rejected"},
                                       {"check_id": "KYC-000001", "applicant_id": "APP-000001", "result": "approved"}]).load()
        self.assertEqual([k["check_id"] for k in data["kyc_by_applicant"]["APP-000001"]], ["KYC-000002", "KYC-000001"])

    def test_conflicting_onboarding_rows_keep_the_first_and_warn(self):
        data = self.folder(onboarding=[
            {"account_id": "ACC-000001", "customer_id": "CUS-000001", "kyc_applicant_id": "APP-000001"},
            {"account_id": "ACC-000001", "customer_id": "CUS-000001", "kyc_applicant_id": "APP-000002"}]).load()
        self.assertEqual(data["applicant_by_account_customer"][("ACC-000001", "CUS-000001")], "APP-000001")
        self.assertTrue(any("two applicants" in w for w in data["warnings"]))


class SearchKeys(FolderTest):
    def test_initials_dropped_words_sorted(self):
        self.assertEqual(search_keys("Mitchell, Charlee D."), ["charlee mitchell"])

    def test_accents_and_hyphens(self):
        self.assertEqual(search_keys("Zoë Müller-Kägi")[0], "kagi muller zoe")
        self.assertEqual(search_keys("Owusu-Ansah, Emmanuel"), ["ansah emmanuel owusu"])

    def test_straight_and_curly_apostrophes_give_the_same_key(self):
        self.assertEqual(search_keys("O'Connor, Michael"), search_keys("O’Connor, Michael"))
        self.assertEqual(search_keys("O’Connor, Michael")[0], "connor michael")

    def test_letters_accent_removal_keeps_give_every_spelling(self):
        keys = search_keys("Drozd, Tomasz Paweł")
        self.assertEqual(keys[0], "drozd pawe tomasz")        # the dev data's form
        self.assertIn("drozd pawel tomasz", keys)
        self.assertIn("soren", search_keys("Søren")[1])
        self.assertEqual(search_keys("Strauß"), ["strauss"])

    def test_names_without_latin_letters_or_blank_give_no_key(self):
        for name in ["محمد علي", "Иван", "", "  ", None, "A. B."]:
            with self.subTest(name=name):
                self.assertEqual(search_keys(name), [])

    def test_find_search_results_tries_every_key_without_repeats(self):
        data = self.folder(search_results=[{"result_id": "SR-000001", "query": "drozd pawe tomasz"},
                                           {"result_id": "SR-000002", "query": "drozd pawel tomasz"},
                                           {"result_id": "SR-000003", "query": "Tomasz  DROZD Pawe"}]).load()
        ids = [r["result_id"] for r in find_search_results(data, "Drozd, Tomasz Paweł")]
        self.assertEqual(ids, ["SR-000001", "SR-000003", "SR-000002"])
        self.assertEqual(find_search_results(data, "محمد"), [])


class HardRules(unittest.TestCase):
    """The AGENTS.md rules, applied to Lane A's modules."""
    LANE_A = ("common.py", "data.py", "link.py", "customer.py")

    def test_no_clock_randomness_network_or_literal_ids(self):
        for filename in self.LANE_A:
            with open(os.path.join(SYSTEM, filename), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    for module in names:
                        self.assertNotIn(module.split(".")[0], {"random", "time", "datetime", "urllib", "http", "socket", "requests"})
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotIn("practice_labels", node.value)
                    self.assertIsNone(re.search(r"\b(?:H|A|ACC|APP|SR|KYC|NOTE)-[0-9A-F]{6}\b|\bCUS-\d{6}\b", node.value))


if __name__ == "__main__":
    unittest.main()
