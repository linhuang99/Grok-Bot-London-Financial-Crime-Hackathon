"""Lane A's additions to system/common.py. Lane B's behaviour is covered in tests/test_lane_b.py."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from common import country_at_end, country_name, dates_agree, parse_date  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
