"""Lane A's fixes to system/hitfacts.py: countries written as places, and ages at a date. Invented hits."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from hitfacts import hit_facts  # noqa: E402


def hit(**fields):
    row = {"hit_id": "H-00000A", "name": "Tom Hale", "entity_type": "Individual", "dobs": [],
           "countries": [], "nationality": [], "citizenship": [], "addresses": [], "categories": ["PEP"],
           "primary_category": "PEP", "profile_notes": ""}
    row.update(fields)
    return row


def facts(row, results=()):
    from data import search_keys
    index = {}
    for r in results:
        index.setdefault(search_keys(r["query"])[0], []).append(r)
    return hit_facts(row, {"search_by_query": index})


class CountriesWrittenAsPlaces(unittest.TestCase):
    def test_a_place_in_any_country_field_gives_its_country(self):
        for field in ("countries", "nationality", "citizenship"):
            with self.subTest(field=field):
                f = facts(hit(**{field: ["Some Town, Some Province, Serbia"]}))
                self.assertEqual([c["value"] for c in f["countries"]], ["Serbia"])
                self.assertEqual(f["quality"]["countries"]["status"], "PARSED")

    def test_official_names_with_commas_and_regions_still_work(self):
        f = facts(hit(nationality=["Korea, Republic of"], countries=["Europe"]))
        self.assertEqual([c["value"] for c in f["countries"]], ["South Korea"])

    def test_an_unknown_place_is_still_flagged(self):
        f = facts(hit(nationality=["Some Town, Atlantis"]))
        self.assertEqual(f["quality"]["countries"]["status"], "UNPARSED")


class BirthYearsFromAnAgeAtADate(unittest.TestCase):
    def test_profile_notes_wording(self):
        f = facts(hit(profile_notes="When investigators questioned Tom Hale in January 2023, he was 46."))
        self.assertEqual([b["value"] for b in f["births"]], [(1976, None, None), (1977, None, None)])
        self.assertEqual(f["birth_source"], "profile")

    def test_search_result_about_the_hit(self):
        result = {"result_id": "SR-00000A", "query": "hale tom", "title": "Tom Hale - report",
                  "snippet": "A regulator's notice from May 2002 listed Tom Hale, 29, a politically exposed person in Serbia."}
        f = facts(hit(nationality=["Belgrade, Serbia"]), [result])
        self.assertEqual([b["value"] for b in f["births"]], [(1972, None, None), (1973, None, None)])
        self.assertEqual({b["source"] for b in f["births"]}, {"SR-00000A"})

    def test_search_result_about_a_namesake_is_ignored(self):
        result = {"result_id": "SR-00000B", "query": "hale tom", "title": "Tom Hale - profile",
                  "snippet": "A local story in February 2010 quoted Tom Hale, 23, a marathon runner in Norway."}
        f = facts(hit(nationality=["Belgrade, Serbia"]), [result])
        self.assertEqual(f["births"], [])

    def test_ambiguous_text_gives_no_birth_year(self):
        f = facts(hit(profile_notes="In May 2002 and June 2003, Tom Hale was 40."))
        self.assertEqual(f["births"], [])

    def test_structured_dobs_still_win(self):
        f = facts(hit(dobs=["1970"], profile_notes="In May 2002, Tom Hale was 40."))
        self.assertEqual([b["value"] for b in f["births"]], [(1970, None, None)])


if __name__ == "__main__":
    unittest.main()
