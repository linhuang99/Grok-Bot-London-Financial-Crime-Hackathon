"""Unit tests for system/link.py on small invented data folders."""
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

from data import load  # noqa: E402
from link import fits_screened, resolve  # noqa: E402


def customer(record_id, name, dob="1985-03-14", **fields):
    row = {"record_id": record_id, "entity_type": "Individual", "full_name": name, "preferred_name": None,
           "login_name": None, "dob": dob, "nationality": "Spain", "residence_country": "ES",
           "city": "Madrid", "address": "1 Calle Mayor, Madrid", "email": record_id.lower() + "@mail.example"}
    row.update(fields)
    return row


def alert(name="Maria Lopez", dob="1985-03-14", country=None, city=None, entity_type="Individual", **links):
    row = {"alert_id": "A-000001", "customer": {"name": name, "entity_type": entity_type, "dob": dob,
                                                "country": country, "city": city},
           "account_ref": None, "login_handle": None, "email": None, "hit_ids": ["H-000001"]}
    row.update(links)
    return row


class LinkTest(unittest.TestCase):
    def data(self, customers, accounts=()):
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path)
        tables = {"alerts": [alert()], "hits": [{"hit_id": "H-000001", "alert_id": "A-000001"}],
                  "customers": customers, "accounts": list(accounts)}
        for name, rows in tables.items():
            with open(os.path.join(path, name + ".jsonl"), "w", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        with open(os.path.join(path, "name_variants.json"), "w", encoding="utf-8") as f:
            json.dump({"groups": [["john", "jon"]], "company_legal_forms": ["ltd", "limited"]}, f)
        with contextlib.redirect_stderr(io.StringIO()):
            return load(path)

    def resolve(self, alert_row, data):
        with contextlib.redirect_stderr(io.StringIO()):
            return resolve(alert_row, data)


class FollowsLinks(LinkTest):
    def test_account_with_one_holder_gives_that_holder(self):
        data = self.data([customer("CUS-000001", "Maria Lopez")],
                         [{"account_id": "ACC-000001", "customer_id": "CUS-000001", "login_handle": "mlopez1"}])
        self.assertEqual(self.resolve(alert(account_ref="ACC-000001"), data), [["CUS-000001"]])

    def test_single_linked_record_is_the_customer_even_if_screened_details_differ(self):
        data = self.data([customer("CUS-000001", "Maria Lopez", dob="1990-01-01")],
                         [{"account_id": "ACC-000001", "customer_id": "CUS-000001", "login_handle": "mlopez1"}])
        self.assertEqual(self.resolve(alert(dob="1985-03-14", account_ref="ACC-000001"), data), [["CUS-000001"]])

    def test_login_gives_its_accounts_holder(self):
        data = self.data([customer("CUS-000001", "Maria Lopez")],
                         [{"account_id": "ACC-000001", "customer_id": "CUS-000001", "login_handle": "mlopez1"}])
        self.assertEqual(self.resolve(alert(login_handle=" MLopez1 "), data), [["CUS-000001"]])

    def test_email_gives_its_customer_ignoring_case_and_spaces(self):
        data = self.data([customer("CUS-000001", "Maria Lopez")])
        self.assertEqual(self.resolve(alert(email=" CUS-000001@Mail.Example"), data), [["CUS-000001"]])

    def test_link_to_nothing_is_searched_like_no_link(self):
        data = self.data([customer("CUS-000001", "Maria Lopez"), customer("CUS-000002", "Jorge Lopez", dob="1979-06-01")])
        self.assertEqual(self.resolve(alert(account_ref="ACC-999999"), data), [["CUS-000001"]])
        self.assertEqual(self.resolve(alert(), data), [["CUS-000001"]])

    def test_link_to_nothing_warns(self):
        data = self.data([customer("CUS-000001", "Maria Lopez")])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            resolve(alert(account_ref="ACC-999999"), data)
        self.assertIn("links to no customer", stderr.getvalue())

    def test_two_links_to_the_same_customer_give_one_person(self):
        data = self.data([customer("CUS-000001", "Maria Lopez")],
                         [{"account_id": "ACC-000001", "customer_id": "CUS-000001", "login_handle": "mlopez1"}])
        self.assertEqual(self.resolve(alert(account_ref="ACC-000001", email="cus-000001@mail.example"), data),
                         [["CUS-000001"]])

    def test_two_links_to_different_customers_are_filtered_by_the_screened_details(self):
        data = self.data([customer("CUS-000001", "Maria Lopez"), customer("CUS-000002", "Jorge Lopez", dob="1979-06-01")],
                         [{"account_id": "ACC-000001", "customer_id": "CUS-000002", "login_handle": "jlopez1"}])
        self.assertEqual(self.resolve(alert(account_ref="ACC-000001", email="cus-000001@mail.example"), data),
                         [["CUS-000001"]])


class JointAccounts(LinkTest):
    def joint(self, *holders):
        return self.data(list(holders), [{"account_id": "ACC-000009", "customer_id": h["record_id"],
                                          "login_handle": "h" + h["record_id"][-1]} for h in holders])

    def test_only_one_holders_name_fits(self):
        data = self.joint(customer("CUS-000001", "Jorge Lopez", dob="1979-06-01"), customer("CUS-000002", "Maria Lopez"))
        self.assertEqual(self.resolve(alert(account_ref="ACC-000009"), data), [["CUS-000002"]])

    def test_same_name_different_date_of_birth_picks_by_date(self):
        data = self.joint(customer("CUS-000001", "John Smith", dob="1960-02-02"),
                          customer("CUS-000002", "John Smith", dob="1990-09-09"))
        self.assertEqual(self.resolve(alert(name="Jon Smith", dob="1990-09-09", account_ref="ACC-000009"), data),
                         [["CUS-000002"]])

    def test_no_holder_fits_finds_nobody(self):
        data = self.joint(customer("CUS-000001", "Jorge Lopez"), customer("CUS-000002", "Ana Lopez"))
        self.assertEqual(self.resolve(alert(account_ref="ACC-000009"), data), [])

    def test_both_holders_fit_gives_two_people_in_file_order(self):
        data = self.joint(customer("CUS-000002", "Maria Lopez"), customer("CUS-000001", "Maria Lopez"))
        self.assertEqual(self.resolve(alert(account_ref="ACC-000009"), data), [["CUS-000002"], ["CUS-000001"]])

    def test_result_is_the_same_every_time(self):
        data = self.joint(customer("CUS-000002", "Maria Lopez"), customer("CUS-000001", "Maria Lopez"))
        self.assertEqual(self.resolve(alert(account_ref="ACC-000009"), data),
                         self.resolve(alert(account_ref="ACC-000009"), data))


class SearchWithoutLink(LinkTest):
    def test_name_must_agree(self):
        data = self.data([customer("CUS-000001", "Jorge Lopez")])
        self.assertEqual(self.resolve(alert(name="Maria Lopez"), data), [])

    def test_nickname_and_typo_still_agree(self):
        data = self.data([customer("CUS-000001", "John Smith", preferred_name="Jon Smith")])
        self.assertEqual(self.resolve(alert(name="Jon Smyth", dob="1985-03-14"), data), [["CUS-000001"]])

    def test_date_of_birth_country_and_city_must_fit(self):
        data = self.data([customer("CUS-000001", "Maria Lopez", dob="1985-03-14"),
                          customer("CUS-000002", "Maria Lopez", dob="1985-03-15"),
                          customer("CUS-000003", "Maria Lopez", residence_country="FR", nationality="French"),
                          customer("CUS-000004", "Maria Lopez", city="Seville", address="2 Calle Sol, Seville")])
        self.assertEqual(self.resolve(alert(dob="1985-03-14", country="Spain", city="Madrid"), data), [["CUS-000001"]])

    def test_entity_type_must_match(self):
        data = self.data([customer("CUS-000001", "Lopez Trading", entity_type="Company")])
        self.assertEqual(self.resolve(alert(name="Lopez Trading", dob=None, entity_type="Individual"), data), [])

    def test_several_fitting_records_give_several_people(self):
        data = self.data([customer("CUS-000002", "Maria Lopez"), customer("CUS-000001", "Maria Lopez")])
        self.assertEqual(self.resolve(alert(), data), [["CUS-000002"], ["CUS-000001"]])

    def test_year_only_screened_date_searches_that_year(self):
        data = self.data([customer("CUS-000001", "Maria Lopez", dob="14/03/1985"),
                          customer("CUS-000002", "Maria Lopez", dob="1986-01-01")])
        self.assertEqual(self.resolve(alert(dob="1985"), data), [["CUS-000001"]])

    def test_no_screened_dob_searches_everyone(self):
        data = self.data([customer("CUS-000001", "Maria Lopez", dob="1990-01-01")])
        self.assertEqual(self.resolve(alert(dob=None), data), [["CUS-000001"]])

    def test_no_screened_name_finds_nobody(self):
        data = self.data([customer("CUS-000001", "Maria Lopez")])
        self.assertEqual(self.resolve(alert(name=None), data), [])


class FitsScreened(LinkTest):
    def setUp(self):
        self.d = self.data([])

    def fits(self, alert_row, record):
        return fits_screened(alert_row, record, self.d)

    def test_preferred_name_fits(self):
        self.assertTrue(self.fits(alert(name="Mia Lopez"), customer("CUS-000001", "Maria Lopez", preferred_name="Mia Lopez")))

    def test_missing_screened_details_never_rule_out(self):
        self.assertTrue(self.fits(alert(name=None, dob=None), customer("CUS-000001", "Someone Else")))

    def test_year_only_screened_date_fits_a_full_date(self):
        self.assertTrue(self.fits(alert(dob="1985"), customer("CUS-000001", "Maria Lopez", dob="14/03/1985")))
        self.assertFalse(self.fits(alert(dob="1986"), customer("CUS-000001", "Maria Lopez", dob="14/03/1985")))

    def test_country_code_and_name_meet(self):
        self.assertTrue(self.fits(alert(country="Spain"), customer("CUS-000001", "Maria Lopez", residence_country="ES")))
        self.assertTrue(self.fits(alert(country="Spain"), customer("CUS-000001", "Maria Lopez",
                                                                    residence_country="FR", nationality="Spanish")))
        self.assertFalse(self.fits(alert(country="Germany"), customer("CUS-000001", "Maria Lopez")))

    def test_unreadable_country_on_either_side_never_rules_out(self):
        self.assertTrue(self.fits(alert(country="Atlantis"), customer("CUS-000001", "Maria Lopez")))
        self.assertTrue(self.fits(alert(country="Germany"), customer("CUS-000001", "Maria Lopez", nationality="Atlantean")))

    def test_city_found_in_address_ignoring_case_and_accents(self):
        record = customer("CUS-000001", "Maria Lopez", city=None, address="4 Rue Haute, Liège")
        self.assertTrue(self.fits(alert(city="LIEGE"), record))
        self.assertFalse(self.fits(alert(city="Lie"), record))  # whole words only
        self.assertFalse(self.fits(alert(city="Namur"), record))

    def test_company_name_fits_without_its_legal_form(self):
        record = customer("CUS-000001", "Brightwater Trading Ltd", entity_type="Company", dob="2001-05-05")
        self.assertTrue(self.fits(alert(name="Brightwater Trading Limited", dob=None, entity_type="Company"), record))


if __name__ == "__main__":
    unittest.main()
