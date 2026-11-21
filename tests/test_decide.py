"""Unit tests for system/decide.py: every rule at its edges, on invented customers and hits.

An unsafe clearance costs 60, so most tests check that a clear is blocked when
the facts it would rest on are incomplete.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from decide import decide  # noqa: E402

DATA = {"name_variants": {"groups": [], "company_legal_forms": ["ltd", "limited"]}}
ALERT = {"alert_id": "A-00000A", "screened_at": "2026-11-06"}
ALL_FIELDS = ("entity_type", "names", "births", "countries")
CODES = {"DIFFERENT_ENTITY": {"TEMPORAL_IMPOSSIBILITY", "DOB_MISMATCH", "LOCATION_MISMATCH", "NAME_MISMATCH_VERIFIED",
                              "ENTITY_TYPE_MISMATCH", "DECEASED"},
         "SAME_ENTITY": {"NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH", "NAME_LOCATION_MATCH"},
         "REVIEW": {"INSUFFICIENT_DATA", "AMBIGUOUS_CUSTOMER_RECORD"}}


def person(rid="CUS-000001", name="Ana Ruiz", dob=(1980, 5, 4), countries=("Spain",), verified=True,
           entity="Individual", complete=ALL_FIELDS, unreadable=()):
    verified_name = {"value": name.upper(), "source": "KYC-000001"} if verified else None
    legal = verified_name or {"value": name, "source": rid}
    return {"record_ids": [rid], "record_id": rid, "entity_type": entity, "verified_name": verified_name,
            "legal_name": legal, "names": [legal],
            "dob": {"value": dob, "source": "KYC-000001" if verified else rid} if dob else None,
            "countries": [{"value": c, "source": rid} for c in countries],
            "unreadable_countries": [{"value": u, "source": rid} for u in unreadable],
            "complete_fields": list(complete)}


def facts(names=("Ana Ruiz",), births=((1980, None, None),), countries=("Spain",), entity="Individual",
          report=None, death=None, partial=()):
    hid = "H-00000A"
    values = {"names": names, "births": births, "countries": countries, "entity_type": [entity] if entity else [],
              "earliest_report": [report] if report else [], "death": [death] if death else []}
    quality, issues = {}, []
    for field, items in values.items():
        parsed, unparsed = len(items), 1 if field in partial else 0
        status = "PARTIAL" if parsed and unparsed else "PARSED" if parsed else "UNPARSED" if unparsed else "MISSING"
        quality[field] = {"status": status, "parsed": parsed, "unparsed": unparsed, "ignored": 0}
        if unparsed:
            issues.append({"field": field, "code": "TEST", "source": hid, "path": field, "blocking": True})
    return {"hit_id": hid, "entity_type": entity, "names": list(names),
            "births": [{"value": b, "source": hid + "#dobs"} for b in births],
            "countries": [{"value": c, "source": hid + "#countries"} for c in countries],
            "earliest_report": {"value": report, "source": hid + "#profile_notes"} if report else None,
            "death": {"value": death, "source": hid + "#deceased_date"} if death else None,
            "quality_version": 1, "quality": quality, "issues": issues}


def run(persons, hit_facts):
    hit = {"hit_id": "H-00000A", "name": hit_facts["names"][0] if hit_facts["names"] else None}
    return decide(ALERT, hit, persons, hit_facts, DATA)


class DecideTest(unittest.TestCase):
    def assertDecision(self, line, decision, code):
        self.assertEqual((line["decision"], line["reason_code"]), (decision, code), line["reason"])


class DateOfBirth(DecideTest):
    def test_every_hit_date_contradicted_clears(self):
        line = run([person()], facts(births=((1970, None, None),), countries=("Spain",)))
        self.assertDecision(line, "DIFFERENT_ENTITY", "DOB_MISMATCH")
        self.assertEqual(line["evidence"], ["CUS-000001", "KYC-000001"])
        self.assertIn("1980-05-04", line["reason"])

    def test_one_year_apart_is_not_a_contradiction(self):
        self.assertDecision(run([person()], facts(births=((1981, None, None),))), "REVIEW", "INSUFFICIENT_DATA")
        self.assertDecision(run([person()], facts(births=((1979, None, None),))), "REVIEW", "INSUFFICIENT_DATA")

    def test_same_year_different_month_or_day_contradicts(self):
        self.assertDecision(run([person()], facts(births=((1980, 6, None),))), "DIFFERENT_ENTITY", "DOB_MISMATCH")
        self.assertDecision(run([person()], facts(births=((1980, 5, 5),))), "DIFFERENT_ENTITY", "DOB_MISMATCH")

    def test_one_agreeing_hit_date_prevents_the_clear(self):
        line = run([person()], facts(births=((1970, None, None), (1980, None, None))))
        self.assertEqual(line["decision"], "SAME_ENTITY")

    def test_blocked_when_either_side_is_incomplete(self):
        hit = facts(births=((1970, None, None),))
        self.assertEqual(run([person(complete=("entity_type", "names", "countries"))], hit)["decision"], "REVIEW")
        self.assertEqual(run([person()], facts(births=((1970, None, None),), partial=("births",)))["decision"], "REVIEW")
        self.assertEqual(run([person(dob=None)], hit)["decision"], "REVIEW")


class TemporalImpossibility(DecideTest):
    def test_younger_than_16_at_the_earliest_report_clears_and_16_does_not(self):
        young = person(dob=(2005, 6, 1))
        self.assertDecision(run([young], facts(births=(), report=(2021, 5, 31))), "DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY")
        self.assertNotEqual(run([young], facts(births=(), report=(2021, 6, 1)))["reason_code"], "TEMPORAL_IMPOSSIBILITY")

    def test_partial_dates_are_taken_at_their_most_cautious(self):
        year_only = person(dob=(2005, None, None))   # could be 1 January 2005
        self.assertNotEqual(run([year_only], facts(births=(), report=(2021, 5, 31)))["reason_code"], "TEMPORAL_IMPOSSIBILITY")
        self.assertDecision(run([year_only], facts(births=(), report=(2020, 12, 31))), "DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY")

    def test_company_incorporated_after_the_report(self):
        company = person(name="Brightwater Trading Ltd", entity="Company", dob=(2015, 1, 1))
        hit = facts(names=("Brightwater Trading",), births=(), entity="Company", report=(2010, 3, 1))
        self.assertDecision(run([company], hit), "DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY")
        same_year = facts(names=("Brightwater Trading",), births=(), entity="Company", report=(2015, 6, None))
        self.assertNotEqual(run([company], same_year)["reason_code"], "TEMPORAL_IMPOSSIBILITY")

    def test_blocked_without_a_complete_customer_birth(self):
        line = run([person(dob=(2005, 6, 1), complete=("entity_type", "names", "countries"))], facts(births=(), report=(2020, 1, 1)))
        self.assertEqual(line["decision"], "REVIEW")


class Deceased(DecideTest):
    def test_death_before_screening_clears(self):
        self.assertDecision(run([person()], facts(births=(), death=(2020, 1, 1))), "DIFFERENT_ENTITY", "DECEASED")

    def test_death_on_the_screening_day_or_possibly_after_does_not(self):
        self.assertNotEqual(run([person()], facts(births=(), death=(2026, 11, 6)))["reason_code"], "DECEASED")
        self.assertNotEqual(run([person()], facts(births=(), death=(2026, None, None)))["reason_code"], "DECEASED")


class Location(DecideTest):
    def test_no_shared_country_clears(self):
        line = run([person(countries=("Spain",))], facts(births=(), countries=("France",)))
        self.assertDecision(line, "DIFFERENT_ENTITY", "LOCATION_MISMATCH")
        self.assertIn("Spain", line["reason"])
        self.assertIn("France", line["reason"])

    def test_name_and_dob_agreeing_overrides_a_country_difference(self):
        line = run([person()], facts(births=((1980, None, None),), countries=("France",)))
        self.assertDecision(line, "REVIEW", "INSUFFICIENT_DATA")

    def test_blocked_by_unreadable_or_incomplete_countries_on_either_side(self):
        hit = facts(births=(), countries=("France",))
        self.assertEqual(run([person(unreadable=("Atlantean",))], hit)["decision"], "REVIEW")
        self.assertEqual(run([person(complete=("entity_type", "names", "births"))], hit)["decision"], "REVIEW")
        self.assertEqual(run([person()], facts(births=(), countries=("France",), partial=("countries",)))["decision"], "REVIEW")

    def test_no_countries_on_a_side_is_not_a_mismatch(self):
        self.assertEqual(run([person(countries=())], facts(births=(), countries=("France",)))["decision"], "REVIEW")


class Names(DecideTest):
    def test_verified_name_agreeing_with_no_hit_name_clears(self):
        line = run([person()], facts(names=("Pedro Gomez", "P. Gomez"), births=()))
        self.assertDecision(line, "DIFFERENT_ENTITY", "NAME_MISMATCH_VERIFIED")
        self.assertIn("KYC-000001", line["evidence"])

    def test_blocked_without_verification_readable_hit_names_or_two_real_parts(self):
        hit = facts(names=("Pedro Gomez",), births=())
        self.assertEqual(run([person(verified=False)], hit)["decision"], "REVIEW")
        self.assertEqual(run([person()], facts(names=("Pedro Gomez",), births=(), partial=("names",)))["decision"], "REVIEW")
        self.assertEqual(run([person(name="Ana")], hit)["decision"], "REVIEW")


class EntityType(DecideTest):
    def test_person_against_company_clears_but_unknown_type_does_not(self):
        self.assertDecision(run([person()], facts(births=(), entity="Company")), "DIFFERENT_ENTITY", "ENTITY_TYPE_MISMATCH")
        self.assertNotEqual(run([person()], facts(births=(), entity=None))["reason_code"], "ENTITY_TYPE_MISMATCH")


class Confirm(DecideTest):
    def test_name_dob_and_country_agree(self):
        self.assertDecision(run([person()], facts()), "SAME_ENTITY", "NAME_DOB_LOCATION_MATCH")

    def test_name_and_dob_agree_with_no_hit_country(self):
        self.assertDecision(run([person()], facts(countries=())), "SAME_ENTITY", "NAME_DOB_MATCH")

    def test_not_confirmed_when_customer_names_or_births_are_incomplete(self):
        self.assertEqual(run([person(complete=("entity_type", "births", "countries"))], facts())["decision"], "REVIEW")
        self.assertEqual(run([person(complete=("entity_type", "names", "countries"))], facts())["decision"], "REVIEW")

    def test_company_name_and_country(self):
        company = person(name="Brightwater Trading Ltd", entity="Company", dob=None)
        self.assertDecision(run([company], facts(names=("Brightwater Trading Limited",), births=(), entity="Company")),
                            "SAME_ENTITY", "NAME_LOCATION_MATCH")


class SeveralOrNoCustomers(DecideTest):
    def test_no_customer_is_review_with_no_record(self):
        line = run([], facts())
        self.assertDecision(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIsNone(line["customer_record_id"])

    def test_several_people_with_the_same_decision_give_it_as_ambiguous(self):
        line = run([person("CUS-000001", countries=("Spain",)), person("CUS-000002", countries=("Italy",))],
                   facts(births=(), countries=("France",)))
        self.assertEqual((line["decision"], line["customer_record_id"]), ("DIFFERENT_ENTITY", "AMBIGUOUS"))

    def test_several_people_with_different_decisions_are_reviewed(self):
        line = run([person("CUS-000001"), person("CUS-000002", countries=("Italy",), dob=(1950, 1, 1))],
                   facts(countries=("Spain",)))
        self.assertDecision(line, "REVIEW", "AMBIGUOUS_CUSTOMER_RECORD")
        self.assertEqual(line["customer_record_id"], "AMBIGUOUS")


class OutputShape(DecideTest):
    CASES = [([person()], facts()), ([person()], facts(births=((1970, None, None),))), ([], facts()),
             ([person()], facts(births=(), countries=("France",))), ([person()], facts(births=((1981, None, None),)))]

    def test_every_line_has_the_official_fields_and_a_code_of_its_decision(self):
        for persons, hit in self.CASES:
            line = run(persons, hit)
            self.assertEqual(set(line), {"hit_id", "alert_id", "decision", "reason_code", "customer_record_id", "reason", "evidence"})
            self.assertIn(line["reason_code"], CODES[line["decision"]])
            self.assertTrue(line["reason"].strip())
            self.assertTrue(all(isinstance(e, str) and e for e in line["evidence"]))

    def test_same_input_same_output(self):
        for persons, hit in self.CASES:
            self.assertEqual(run(persons, hit), run(persons, hit))


if __name__ == "__main__":
    unittest.main()
