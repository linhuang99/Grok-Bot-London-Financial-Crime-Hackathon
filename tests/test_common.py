"""Lane A's additions to system/common.py. Lane B's behaviour is covered in tests/test_lane_b.py."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from common import ages_at_dates, country_at_end, country_name, dates_agree, parse_date  # noqa: E402


class DatesAgree(unittest.TestCase):
    def test_year_only_agrees_with_any_date_in_that_year(self):
        self.assertTrue(dates_agree((1990, None, None), (1990, 5, 4)))
        self.assertTrue(dates_agree((1990, 5, 4), (1990, None, None)))

    def test_equal_dates_agree(self):
        self.assertTrue(dates_agree((1990, 5, 4), (1990, 5, 4)))

    def test_any_part_both_give_that_differs_disagrees(self):
        self.assertFalse(dates_agree((1990, 5, 4), (1990, 5, 5)))
        self.assertFalse(dates_agree((1990, 5, None), (1990, 6, 1)))
        self.assertFalse(dates_agree((1990, None, None), (1991, 1, 1)))

    def test_parts_only_one_side_gives_never_disagree(self):
        self.assertTrue(dates_agree((1990, 5, None), (1990, None, 17)))

    def test_works_on_parsed_dates_in_different_formats(self):
        self.assertTrue(dates_agree(parse_date("04/05/1990"), parse_date("May 4, 1990")))
        self.assertTrue(dates_agree(parse_date("1990"), parse_date("4 May 1990")))


class PlaceholdersAreNotCountries(unittest.TestCase):
    def test_placeholders_give_none(self):
        for text in ["NA", "na", "N/A", "n/a", "Unknown", "UNKNOWN", "None", "Not known", "TBC", "XX", "Test"]:
            with self.subTest(text=text):
                self.assertIsNone(country_name(text))

    def test_placeholder_at_the_end_of_an_address_gives_none(self):
        self.assertIsNone(country_at_end("Some Street, Some Town, N/A"))

    def test_namibia_written_out_still_works(self):
        self.assertEqual(country_name("Namibia"), "Namibia")

    def test_real_two_letter_codes_still_work(self):
        self.assertEqual(country_name("NG"), "Nigeria")
        self.assertEqual(country_name("GB"), "United Kingdom")


class ImplausibleYears(unittest.TestCase):
    def test_years_outside_1800_to_2100_stay_unknown(self):
        for text in ["0099", "1799", "1700-01-01", "12 March 1700", "2101", "31/12/2200"]:
            with self.subTest(text=text):
                self.assertIsNone(parse_date(text))
        self.assertIsNone(parse_date((99, None, None)))

    def test_boundary_years_parse(self):
        self.assertEqual(parse_date("1800"), (1800, None, None))
        self.assertEqual(parse_date("31/12/2100"), (2100, 12, 31))


class AgesAtDates(unittest.TestCase):
    """One age and one date in a text give the age at that date. Invented names."""

    def test_every_wording_seen_in_the_data(self):
        cases = [
            ("November 1998 saw Ana Ruiz, a 30-year-old, face charges.", 30, (1998, 11, None)),
            ("When investigators questioned Tom Hale in January 2023, he was 46.", 46, (2023, 1, None)),
            ("Investigators questioned Tom Hale in January 2025, when he reached the age of 38.", 38, (2025, 1, None)),
            ("Questioned in April 2006, Tom Hale was 42 years old.", 42, (2006, 4, None)),
            ("May 2019 news reports profiled 33 year old TOM HALE, a PEP in Brazil.", 33, (2019, 5, None)),
            ("In February 2010, at the age of 33, Tom Hale was profiled.", 33, (2010, 2, None)),
            ("Tom Hale, 52, who was named in adverse media, appeared in a list from June 2012.", 52, (2012, 6, None)),
            ("In October 2006 a newspaper interviewed 26, Maria Miller, a taxi driver.", 26, (2006, 10, None)),
            ("Charges were brought against Ana Ruiz, aged 30, in November 1998.", 30, (1998, 11, None)),
            ("November 1981 marked the date Pere Vila, then 37, was placed under charge.", 37, (1981, 11, None)),
        ]
        for text, age, date in cases:
            with self.subTest(text=text):
                self.assertEqual(ages_at_dates(text), [(age, date)])

    def test_ambiguous_texts_give_nothing(self):
        for text in ["In May 2002 and June 2003 he was 40.",            # two dates
                     "Aged 30 and aged 31, both questioned in May 2002.",  # two ages
                     "In May 2002 he was 140.",                         # implausible age
                     "In 2002 he was 40.",                              # a bare year is not a date
                     "He was 40.",                                      # no date
                     "", None]:
            with self.subTest(text=text):
                self.assertEqual(ages_at_dates(text), [])

    def test_numbers_that_are_not_ages(self):
        for text in ["In March 2019 he was 3 times convicted.",
                     "In May 2002 the loss was 4,600 pounds.",
                     "Fined 1,250,000, in May 2002.",
                     "In May 2002 he was fined 12, plus costs.",
                     "Federal Register notice: Vol. 74, No. 11, imposed 1/9/2009."]:
            with self.subTest(text=text):
                self.assertEqual(ages_at_dates(text), [])


if __name__ == "__main__":
    unittest.main()
