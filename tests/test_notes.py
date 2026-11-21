"""Unit tests for system/notes.py and how customer.py uses notes. Invented people only."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from common import find_dates  # noqa: E402
from customer import person  # noqa: E402
from data import load  # noqa: E402
from notes import kyc_check, lived_in, verified_name  # noqa: E402


def kyc(text, note_id="NOTE-000001"):
    return kyc_check({"note_id": note_id, "channel": "kyc", "text": text})


class KycNotes(unittest.TestCase):
    def test_wordings_seen_in_the_data(self):
        cases = [
            ("Persona validated the passport from Italy for EVA ROSSI (DOB 17 June 1976) on 2025-12-24.",
             "EVA ROSSI", "17 June 1976", "2025-12-24", "Italy"),
            ("DOB August 6, 1967 validated via Sumsub on 2024-05-10 per driving licence from Germany for ANNA KLEIN.",
             "ANNA KLEIN", "August 6, 1967", "2024-05-10", "Germany"),
            ("AMAKA OBI's identity was confirmed via Veriff on 2024-04-26 using a Nigerian national ID. DOB recorded as 10/08/1988.",
             "AMAKA OBI", "10/08/1988", "2024-04-26", "Nigeria"),
            ("ID verification (Sumsub, 2025-02-25) approved. Document: passport (France). Name on document: MIKAEL DURAND. "
             "Date of birth on document: October 7, 1988.", "MIKAEL DURAND", "October 7, 1988", "2025-02-25", "France"),
        ]
        for text, name, dob, checked, country in cases:
            with self.subTest(text=text[:40]):
                check = kyc(text)
                self.assertEqual((check["verified_name"], check["verified_dob"], check["checked_at"], check["document_country"]),
                                 (name, dob, checked, country))
                self.assertEqual((check["check_id"], check["result"]), ("NOTE-000001", "approved"))

    def test_earlier_date_is_the_birth_date_whatever_the_order(self):
        check = kyc("Checked on 2024-01-02: LUCA BIANCHI, passport from Italy, born 3 March 1990.")
        self.assertEqual((check["verified_dob"], check["checked_at"]), ("3 March 1990", "2024-01-02"))

    def test_accented_capital_names(self):
        self.assertEqual(verified_name("The Persona system validated FERNÁNDEZ ISABEL, DOB April 23, 1970."),
                         "FERNÁNDEZ ISABEL")
        self.assertEqual(verified_name("Verified PAWEŁ NOWAK on 2024-01-01."), "PAWEŁ NOWAK")

    def test_no_name_or_two_names_or_placeholders_give_no_name(self):
        for text in ["Verified the customer on 2024-01-01, born 1 May 1980.",
                     "ANNA KLEIN and PETER KLEIN were verified on 2024-01-01.",
                     "Verification for N/A GILBERT, born May 21, 1995, was approved.",
                     "Sumsub confirmed the identity of SANI 0000 0000 on 2024-05-17."]:
            with self.subTest(text=text):
                self.assertIsNone(verified_name(text))

    def test_capitalised_countries_and_codes_are_not_names(self):
        self.assertEqual(verified_name("UNITED STATES passport for JOHN SMITH, DOB 1 May 1980, KYC ID ok."), "JOHN SMITH")

    def test_single_date_is_birth_only_with_a_birth_word(self):
        self.assertEqual((kyc("ANNA KLEIN, born 1 May 1980, verified.")["verified_dob"],
                          kyc("ANNA KLEIN, born 1 May 1980, verified.")["checked_at"]), ("1 May 1980", None))
        self.assertEqual((kyc("ANNA KLEIN verified on 2024-01-01.")["verified_dob"],
                          kyc("ANNA KLEIN verified on 2024-01-01.")["checked_at"]), (None, "2024-01-01"))

    def test_no_dates_and_no_country(self):
        check = kyc("ANNA KLEIN was verified.")
        self.assertEqual((check["verified_dob"], check["checked_at"], check["document_country"], check["note_countries"]),
                         (None, None, None, []))


class LivedIn(unittest.TestCase):
    def test_every_country_a_note_mentions_counts_however_it_is_worded(self):
        for text, expected in [("The customer lived and worked in Ghana from 2014 to 2018.", ["Ghana"]),
                               ("The client spent the years 2016 to 2021 employed and dwelling in Romania.", ["Romania"]),
                               ("Employment and housing in Austria were active from 2017 to 2019.", ["Austria"]),
                               ("A Nigerian national, previously in Kenya.", ["Kenya", "Nigeria"]),
                               ("Customer lived in the UK and then the USA.", ["United Kingdom", "United States"]),
                               ("Customer asked about savings interest rates.", [])]:
            with self.subTest(text=text):
                self.assertEqual(lived_in({"note_id": "NOTE-000001", "channel": "email", "text": text}), expected)

    def test_us_as_a_word_is_not_the_united_states(self):
        self.assertEqual(lived_in({"text": "Please contact us about the transfer."}), [])


class FindDates(unittest.TestCase):
    def test_formats_and_look_alikes(self):
        self.assertEqual([d for _, d in find_dates("born 4th May 1990, checked 2024-01-02, DOB Sept. 12, 1971")],
                         [(1990, 5, 4), (2024, 1, 2), (1971, 9, 12)])
        self.assertEqual(find_dates("ref 2024-05-1012, code 12/05/90, year 1990"), [])


class CustomerUsesNotes(unittest.TestCase):
    def data(self, notes, checks=()):
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path)
        customers = [{"record_id": "CUS-000001", "entity_type": "Individual", "full_name": "Anna Klein",
                      "dob": "1980-05-01", "nationality": "German", "residence_country": "DE", "email": "anna@mail.example"},
                     {"record_id": "CUS-000002", "entity_type": "Individual", "full_name": "Other Person",
                      "dob": "1970-01-01", "nationality": "French", "residence_country": "FR", "email": "other@mail.example"}]
        tables = {"alerts": [], "hits": [], "customers": customers,
                  "accounts": [{"account_id": "ACC-000001", "customer_id": "CUS-000001"}],
                  "onboarding": [{"account_id": "ACC-000001", "customer_id": "CUS-000001", "kyc_applicant_id": "APP-000001"}],
                  "kyc_checks": list(checks), "notes": notes}
        for name, rows in tables.items():
            with open(os.path.join(path, name + ".jsonl"), "w", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        with contextlib.redirect_stderr(io.StringIO()):
            return load(path)

    KYC_NOTE = {"note_id": "NOTE-000001", "requester_email": "anna@mail.example", "channel": "kyc",
                "text": "Sumsub verified ANNA MARIA KLEIN, born 2 May 1980, on 2025-03-01 using a passport from Austria."}

    def test_kyc_note_gives_the_verified_identity(self):
        p = person(["CUS-000001"], self.data([self.KYC_NOTE]))
        self.assertEqual(p["verified_name"], {"value": "ANNA MARIA KLEIN", "source": "NOTE-000001"})
        self.assertEqual(p["dob"], {"value": (1980, 5, 2), "source": "NOTE-000001"})
        self.assertIn({"value": "Austria", "source": "NOTE-000001"}, p["countries"])
        self.assertIn("names", p["complete_fields"])

    def test_newer_note_beats_older_table_check_and_older_note_loses(self):
        table = {"check_id": "KYC-000001", "applicant_id": "APP-000001", "verified_name": "ANNA KLEIN",
                 "verified_dob": "1980-05-01", "document_country": "Germany", "result": "approved"}
        newer = person(["CUS-000001"], self.data([self.KYC_NOTE], [dict(table, checked_at="2020-01-01")]))
        older = person(["CUS-000001"], self.data([self.KYC_NOTE], [dict(table, checked_at="2026-01-01")]))
        self.assertEqual(newer["verified_name"]["source"], "NOTE-000001")
        self.assertEqual(older["verified_name"]["source"], "KYC-000001")

    def test_another_customers_note_is_never_used(self):
        p = person(["CUS-000002"], self.data([self.KYC_NOTE]))
        self.assertIsNone(p["verified_name"])

    def test_lived_in_note_adds_a_country(self):
        note = {"note_id": "NOTE-000002", "requester_email": "anna@mail.example", "channel": "phone",
                "text": "The customer maintained residence and employment in Ghana for 2014 to 2018."}
        p = person(["CUS-000001"], self.data([note]))
        self.assertIn({"value": "Ghana", "source": "NOTE-000002"}, p["countries"])

    def test_unreadable_name_in_the_latest_check_makes_names_incomplete(self):
        note = dict(self.KYC_NOTE, text="Sumsub verified the customer, born 2 May 1980, on 2025-03-01.")
        p = person(["CUS-000001"], self.data([note]))
        self.assertNotIn("names", p["complete_fields"])
        self.assertIn("births", p["complete_fields"])


if __name__ == "__main__":
    unittest.main()
