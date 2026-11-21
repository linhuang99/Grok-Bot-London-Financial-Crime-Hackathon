"""Policy-facing Lane B tests. All people, records and snippets are synthetic.

Run with python3 -m unittest discover tests. No participant data, labels, API,
wall clock, installed dependencies or alternative scoring implementation.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system'))
from common import (parse_date, country_name, country_at_end, country_parse_status,
                    countries_in_text, search_query, field_is_complete)
from names import names_agree, company_names_agree, name_parts, usable_individual_name
from hitfacts import hit_facts

VARIANTS = {'groups': [['robert', 'bob'], ['mohammed', 'muhammad']],
            'company_legal_forms': ['ltd', 'limited', 'ab', 'sa']}


def make_hit(**changes):
    hit = {'hit_id': 'H-ABCDEF', 'name': 'Example Person', 'aliases': [],
           'entity_type': 'Individual', 'dobs': [], 'countries': ['GB']}
    hit.update(changes)
    return hit


def extract(hit=None, data=None):
    return hit_facts(hit if hit is not None else make_hit(),
                     data if data is not None else {'search_by_query': {}})


def values(facts, field):
    return [f['value'] for f in facts[field]]


def state(facts, field):
    return facts['quality'][field]['status']


def search_data(*rows):
    query = search_query('Example Person')
    return {'search_by_query': {query: [dict(query=query, **row) for row in rows]}}


def result(rid='SR-SYNTHETIC', text='A politically exposed person in United Kingdom, born in 1970.'):
    return {'result_id': rid, 'title': 'Example Person', 'snippet': text}


class DateParsing(unittest.TestCase):
    def test_full_dates_and_english_formats(self):
        for text in ['1984-02-29', '29/02/1984', '29 February 1984', 'February 29, 1984',
                     '29 Feb 1984', 'Feb 29 1984', '29th February 1984']:
            with self.subTest(text=text): self.assertEqual(parse_date(text), (1984,2,29))

    def test_partial_dates_do_not_invent_parts(self):
        for text, date in [('1984',(1984,None,None)), ('1984-02',(1984,2,None)),
                           ('February 1984',(1984,2,None))]:
            with self.subTest(text=text): self.assertEqual(parse_date(text), date)

    def test_invalid_dates_do_not_become_valid_years(self):
        for text in ['1983-02-29','1984-13','1984-02-31','1984-00-01','31/04/1984','01/02/84','unknown','']:
            with self.subTest(text=text): self.assertIsNone(parse_date(text))

    def test_partial_date_type_is_strict(self):
        for value in [(1984.9,2,1),(True,2,1),(1984,None,1), {'year':1984}, [1984,2], None]:
            with self.subTest(value=value): self.assertIsNone(parse_date(value))
        self.assertEqual(parse_date((1984,2,None)), (1984,2,None))


class CountryParsing(unittest.TestCase):
    def test_codes_names_and_demonyms(self):
        for text in ['GB','UK','GBR','British','United Kingdom']:
            with self.subTest(text=text): self.assertEqual(country_name(text),'United Kingdom')
        self.assertEqual(country_name('Russian'),'Russia')
        self.assertEqual(country_name('USA'),'United States')

    def test_regions_are_ignored_but_unknown_country_is_unparsed(self):
        self.assertEqual(country_parse_status(None), ('MISSING',None))
        self.assertEqual(country_parse_status('Europe'), ('IGNORED',None))
        self.assertEqual(country_parse_status('International [Associated]'), ('IGNORED',None))
        self.assertEqual(country_parse_status('Unrecognisedland'), ('UNPARSED',None))
        self.assertEqual(country_parse_status({'country':'GB'}), ('UNPARSED',None))

    def test_role_labels_and_final_address_component(self):
        self.assertEqual(country_name('United States [Associated]'),'United States')
        self.assertEqual(country_at_end('Example City, GB [Residency]'),'United Kingdom')
        self.assertIsNone(country_at_end('Example City, Unrecognisedland'))

    def test_territories_are_not_parent_countries(self):
        self.assertNotEqual(country_name('HK'),country_name('CN'))
        self.assertEqual(country_name('XK'),'Kosovo')
        self.assertEqual(country_name('Macao Special Administrative Region of China'),'Macao')
        self.assertEqual(country_name('Trinidad and Tobago'),'Trinidad and Tobago')

    def test_prose_matches_boundaries_and_longest_country(self):
        self.assertEqual(countries_in_text('A North Korean official.'), {'North Korea'})
        self.assertEqual(countries_in_text('Macao Special Administrative Region of China'), {'Macao'})
        self.assertNotIn('United States',countries_in_text('A Russian official.'))
        self.assertEqual(countries_in_text('In Nigeria and the United Kingdom.'), {'Nigeria','United Kingdom'})


class NameMatching(unittest.TestCase):
    def agree(self, a, b): return names_agree(a,b,VARIANTS)

    def test_case_accents_initials_brackets_and_order(self):
        self.assertTrue(self.agree('José A. Silva (archived)','Silva Jose'))
        self.assertTrue(self.agree('Robert Stone [old (closed)]','Stone Robert'))

    def test_placeholders_digits_and_repetitions(self):
        self.assertEqual(name_parts('NA N/A TEST UNKNOWN XXX NONE 123 AB123 A.'), ())
        self.assertEqual(name_parts('Rose Rose Tyler'), ('rose','tyler'))
        self.assertFalse(self.agree('UNKNOWN','UNKNOWN'))
        self.assertEqual(name_parts({'name':'Example Person'}), ())

    def test_variants_and_single_part_hit_alias(self):
        self.assertTrue(self.agree('Bob Stone','Robert Stone'))
        self.assertTrue(self.agree('Khan Muhammad','Mohammed Khan'))
        self.assertTrue(self.agree('Robert Stone','Bob'))

    def test_customer_name_sufficiency_is_a_separate_gate(self):
        self.assertFalse(usable_individual_name('Bob'))
        self.assertFalse(usable_individual_name('A. TEST Stone'))
        self.assertTrue(usable_individual_name('Robert Stone'))

    def test_shorter_part_length_controls_edit_allowance(self):
        self.assertFalse(self.agree('Li','Lu'))
        self.assertFalse(self.agree('Ann','Anne'))
        self.assertTrue(self.agree('Marta','Martha'))
        self.assertFalse(self.agree('Marta','Matra'))  # transposition is two edits
        self.assertTrue(self.agree('Jonathan','Jonathen'))
        self.assertTrue(self.agree('Jonathan','Jonethen'))  # two edits, seven+ letters

    def test_one_matching_part_does_not_clear_two_part_requirement(self):
        self.assertFalse(self.agree('Marta Zed','Martha Rex'))
        self.assertTrue(self.agree('Marta Zed','Martha Zed'))
        self.assertTrue(self.agree('Robert Stone Extra','Stone Robert Another'))

    def test_split_join_counts_once_without_reusing_parts(self):
        self.assertTrue(self.agree('Abdulsalam Stone','Abdul Salam Stone'))
        self.assertTrue(self.agree('Abdulsalam','Abdul Salam'))
        self.assertFalse(self.agree('Abdulsalam Zed','Abdul Salam Rex'))
        self.assertFalse(self.agree('Robert Bob','Robert Zed'))

    def test_company_legal_forms_are_not_personal_name_stopwords(self):
        self.assertTrue(company_names_agree('Silver Orchard Ltd','Orchard Silver AB',VARIANTS))
        self.assertFalse(company_names_agree('Orchard Ltd','Mountain Ltd',VARIANTS))
        self.assertIn('sa',name_parts('Sa Stone',VARIANTS))

    def test_non_string_names_cannot_become_name_parts(self):
        for value in [None,123,True,{'name':'Example Person'},['Example','Person']]:
            with self.subTest(value=value):
                self.assertEqual(name_parts(value),())
                self.assertFalse(names_agree(value,'Example Person',VARIANTS))

    def test_symmetry(self):
        for a,b in [('Abdul Salam','Abdulsalam'),('Bob Stone','Robert Stone'),('Marta Zed','Martha Rex')]:
            with self.subTest(a=a,b=b): self.assertEqual(self.agree(a,b),self.agree(b,a))


class FactExtraction(unittest.TestCase):
    def test_structured_dates_take_precedence_over_profile_and_search(self):
        h=make_hit(dobs=['1984'],profile_notes='Born in 1920.',primary_category='PEP')
        f=extract(h,search_data(result()))
        self.assertEqual(values(f,'births'),[(1984,None,None)])
        self.assertEqual(f['birth_source'],'structured')
        self.assertEqual(f['births'][0]['source'],'H-ABCDEF#dobs')

    def test_all_possible_dates_are_preserved(self):
        f=extract(make_hit(dobs=['1984','1985-03','1984']))
        self.assertEqual(set(values(f,'births')),{(1984,None,None),(1985,3,None)})
        self.assertEqual(state(f,'births'),'PARSED')
        self.assertFalse(any(i['code']=='UNRESOLVED_SOURCE_CONFLICT' for i in f['issues']))

    def test_profile_full_birth_and_age_uncertainty(self):
        f=extract(make_hit(profile_notes='Born on 14 March 1984.'))
        self.assertEqual(values(f,'births'),[(1984,3,14)])
        f=extract(make_hit(profile_notes='Aged 45 when sentenced in March 2019.'))
        self.assertEqual(set(values(f,'births')),{(1973,None,None),(1974,None,None)})
        self.assertEqual(f['birth_source'],'profile')

    def test_dob_abbreviation(self):
        f=extract(make_hit(profile_notes='D.O.B.: 14 March 1984.'))
        self.assertEqual(values(f,'births'),[(1984,3,14)])

    def test_only_first_biographical_paragraph_supplies_birth(self):
        f=extract(make_hit(profile_notes='No biographical date.\n\nSomeone else was born in 1920.'))
        self.assertEqual(f['births'],[])
        self.assertEqual(state(f,'births'),'MISSING')
        f=extract(make_hit(profile_notes='According to Example News; March 12, 2019: born in 1920.'))
        self.assertEqual(f['births'],[])

    def test_company_incorporation_only_from_structured_dates(self):
        f=extract(make_hit(entity_type='Company',profile_notes='Born in 1920.'))
        self.assertEqual(f['births'],[])
        f=extract(make_hit(entity_type='Company',dobs=['1999-03']))
        self.assertEqual(values(f,'births'),[(1999,3,None)])

    def test_exact_english_reports_and_earliest_date(self):
        f=extract(make_hit(profile_notes='Biography.\nAccording to Example News; March 12, 2019: event.\nAccording to Example Wire; May 4, 2017: event.\nReported on January 1, 1900.'))
        self.assertEqual(f['earliest_report']['value'],(2017,5,4))
        self.assertEqual(state(f,'earliest_report'),'PARSED')

    def test_non_policy_reports_do_not_supply_temporal_evidence(self):
        for text in ['According to News; June 2018: event.', 'Reported on January 1, 1900.']:
            f=extract(make_hit(profile_notes=text))
            self.assertIsNone(f['earliest_report'])
            self.assertEqual(state(f,'earliest_report'),'MISSING')

    def test_all_country_fields_and_provenance(self):
        f=extract(make_hit(countries=['GB'],nationality=['US'],citizenship=['Nigeria'],
                          addresses=['Example City, HK'],place_of_birth='Example City, Macao'))
        self.assertEqual(set(values(f,'countries')),{'United Kingdom','United States','Nigeria','Hong Kong','Macao'})
        self.assertTrue(all(x['source'].startswith('H-ABCDEF#') for x in f['countries']))
        self.assertTrue(field_is_complete(f,'countries'))

    def test_name_sources_preserve_component_provenance(self):
        f=extract(make_hit(first_name='Sample',last_name='Name',aliases=['Alias Name']))
        self.assertIn('Sample Name',f['names'])
        self.assertEqual(f['name_sources']['Sample Name'],['H-ABCDEF#first_name','H-ABCDEF#last_name'])
        self.assertEqual(f['name_sources']['Alias Name'],['H-ABCDEF#aliases'])

    def test_death_date_preserves_precision(self):
        f=extract(make_hit(deceased_date='2020-02'))
        self.assertEqual(f['death']['value'],(2020,2,None))
        self.assertEqual(f['death']['source'],'H-ABCDEF#deceased_date')


class QualityContract(unittest.TestCase):
    def test_missing_parsed_partial_and_unparsed_country_states(self):
        cases=[([], 'MISSING'), (['GB'], 'PARSED'),
               (['GB','Unrecognisedland'],'PARTIAL'), (['Unrecognisedland'],'UNPARSED')]
        for countries,expected in cases:
            with self.subTest(countries=countries):
                f=extract(make_hit(countries=countries))
                self.assertEqual(state(f,'countries'),expected)
                self.assertEqual(field_is_complete(f,'countries'),expected=='PARSED')

    def test_regions_are_ignored_not_unparsed(self):
        f=extract(make_hit(countries=['GB','Europe','International']))
        self.assertEqual(state(f,'countries'),'PARSED')
        self.assertEqual(f['quality']['countries']['ignored'],2)
        self.assertFalse(any(i['field']=='countries' for i in f['issues']))

    def test_known_facts_survive_partial_country_failure(self):
        f=extract(make_hit(countries=['GB','Unrecognisedland']))
        self.assertEqual(values(f,'countries'),['United Kingdom'])
        issue=next(i for i in f['issues'] if i['field']=='countries')
        self.assertEqual((issue['source'],issue['path'],issue['blocking']),('H-ABCDEF#countries','countries',True))
        self.assertNotIn('raw',issue)

    def test_malformed_country_field_does_not_crash_or_disappear(self):
        f=extract(make_hit(countries=[{'country':'GB'}]))
        self.assertEqual(state(f,'countries'),'UNPARSED')
        self.assertFalse(field_is_complete(f,'countries'))

    def test_invalid_date_alternative_blocks_birth_contradiction(self):
        f=extract(make_hit(dobs=['1984','1985-02-31']))
        self.assertEqual(values(f,'births'),[(1984,None,None)])
        self.assertEqual(state(f,'births'),'PARTIAL')
        self.assertFalse(field_is_complete(f,'births'))

    def test_fallback_success_does_not_erase_structured_failure(self):
        f=extract(make_hit(dobs=['not a date'],profile_notes='Born in 1984.'))
        self.assertEqual(f['birth_source'],'profile')
        self.assertEqual(state(f,'births'),'PARTIAL')
        self.assertFalse(field_is_complete(f,'births'))

    def test_unsupported_birth_expression_is_not_missing(self):
        f=extract(make_hit(profile_notes='Born in an unknown season.'))
        self.assertEqual(state(f,'births'),'UNPARSED')
        self.assertIn('UNSUPPORTED_BIRTH_EXPRESSION',[i['code'] for i in f['issues']])

    def test_invalid_exact_report_blocks_temporal_completeness(self):
        f=extract(make_hit(profile_notes='According to News; February 31, 2010: event.\nAccording to News; March 1, 2012: event.'))
        self.assertEqual(f['earliest_report']['value'],(2012,3,1))
        self.assertEqual(state(f,'earliest_report'),'PARTIAL')
        self.assertFalse(field_is_complete(f,'earliest_report'))

    def test_invalid_death_date_does_not_become_missing(self):
        f=extract(make_hit(deceased_date='2020-02-31'))
        self.assertIsNone(f['death'])
        self.assertEqual(state(f,'death'),'UNPARSED')

    def test_missing_and_unknown_entity_type(self):
        f=extract(make_hit(entity_type=None,profile_notes='Born in 1984.'))
        self.assertIsNone(f['entity_type'])
        self.assertEqual(state(f,'entity_type'),'MISSING')
        self.assertEqual(f['births'],[])
        f=extract(make_hit(entity_type='UnrecognisedType'))
        self.assertIsNone(f['entity_type'])
        self.assertEqual(state(f,'entity_type'),'UNPARSED')

    def test_malformed_names_block_name_clearance(self):
        f=extract(make_hit(aliases=[{'name':'Different Person'}]))
        self.assertIn('Example Person',f['names'])
        self.assertEqual(state(f,'names'),'PARTIAL')
        self.assertFalse(field_is_complete(f,'names'))

    def test_placeholder_names_are_ignored_not_a_mismatch(self):
        f=extract(make_hit(name='UNKNOWN',aliases=['N/A','123']))
        self.assertEqual(f['names'],[])
        self.assertEqual(state(f,'names'),'MISSING')
        self.assertFalse(field_is_complete(f,'names'))

    def test_unknown_quality_version_and_malformed_metadata_fail_closed(self):
        f=extract(make_hit(dobs=['1984']))
        self.assertEqual(f['quality_version'],1)
        for change in [{'quality_version':2}, {'quality':None}, {'issues':None},
                       {'issues':[None]}, {'quality':{'births':'PARSED'}}]:
            with self.subTest(change=change):
                self.assertFalse(field_is_complete(dict(f,**change),'births'))

    def test_country_problem_does_not_globally_block_valid_births(self):
        f=extract(make_hit(dobs=['1984'],countries=['Unrecognisedland']))
        self.assertFalse(field_is_complete(f,'countries'))
        self.assertTrue(field_is_complete(f,'births'))

    def test_conflict_and_legacy_quality_fail_closed(self):
        self.assertFalse(field_is_complete({'births':[{'value':(1984,None,None),'source':'S'}]},'births'))
        f=extract(make_hit(dobs=['1984']))
        f['issues'].append({'field':'births','code':'UNRESOLVED_SOURCE_CONFLICT','source':'S','path':'birth','blocking':True})
        self.assertFalse(field_is_complete(f,'births'))

    def test_no_search_index_is_not_the_same_as_no_results(self):
        self.assertEqual(state(hit_facts(make_hit(),{}),'births'),'UNPARSED')
        self.assertEqual(state(extract(),'births'),'MISSING')

    def test_malformed_profile_notes_are_reported(self):
        f=extract(make_hit(profile_notes={'text':'Born in 1984.'}))
        self.assertEqual(state(f,'births'),'UNPARSED')
        self.assertEqual(state(f,'earliest_report'),'UNPARSED')


class SearchFallback(unittest.TestCase):
    def test_matching_name_listing_and_country_required(self):
        data=search_data(result(),result('SR-OTHER-COUNTRY','A politically exposed person in Nigeria, born in 1990.'),
                         result('SR-OTHER-KIND','A musician in United Kingdom, born in 1995.'))
        f=extract(make_hit(primary_category='PEP'),data)
        self.assertEqual(values(f,'births'),[(1970,None,None)])
        self.assertEqual(f['births'][0]['source'],'SR-SYNTHETIC')
        self.assertEqual(f['birth_source'],'search')

    def test_category_fallback_to_first_category(self):
        f=extract(make_hit(categories=['PEP'],primary_category=None),search_data(result()))
        self.assertEqual(values(f,'births'),[(1970,None,None)])

    def test_other_category_uses_policy_generic_phrase(self):
        f=extract(make_hit(categories=['Registration']),search_data(result(text='Named on a watchlist in United Kingdom; born in 1970.')))
        self.assertEqual(values(f,'births'),[(1970,None,None)])

    def test_country_not_known_cannot_accept_search_birth(self):
        f=extract(make_hit(countries=[],primary_category='PEP'),search_data(result()))
        self.assertEqual(f['births'],[])
        self.assertFalse(field_is_complete(f,'births'))

    def test_wrong_query_bucket_is_not_trusted(self):
        data=search_data(result());data['search_by_query'][search_query('Example Person')][0]['query']='another person'
        f=extract(make_hit(primary_category='PEP'),data)
        self.assertEqual(f['births'],[])
        self.assertEqual(state(f,'births'),'UNPARSED')

    def test_duplicate_id_with_conflicting_payload_is_not_first_row_wins(self):
        a=result();b=result(text='A politically exposed person in United Kingdom, born in 1990.')
        h=make_hit(primary_category='PEP')
        first=extract(h,search_data(a,b));second=extract(h,search_data(b,a))
        self.assertEqual(first,second)
        self.assertEqual(first['births'],[])
        self.assertIn('UNRESOLVED_SOURCE_CONFLICT',[i['code'] for i in first['issues']])

    def test_duplicate_identical_results_do_not_duplicate_facts(self):
        f=extract(make_hit(primary_category='PEP'),search_data(result(),result()))
        self.assertEqual(len(f['births']),1)

    def test_search_does_not_override_profile_birth(self):
        f=extract(make_hit(primary_category='PEP',profile_notes='Born in 1984.'),search_data(result()))
        self.assertEqual(values(f,'births'),[(1984,None,None)])
        self.assertEqual(f['birth_source'],'profile')

    def test_unparsed_search_alternative_blocks_complete_birth_set(self):
        f=extract(make_hit(primary_category='PEP'),search_data(result(),result('SR-BAD','A politically exposed person in United Kingdom, born in an unknown season.')))
        self.assertEqual(state(f,'births'),'PARTIAL')
        self.assertFalse(field_is_complete(f,'births'))

    def test_malformed_search_text_is_not_silently_empty(self):
        f=extract(make_hit(primary_category='PEP'),search_data(dict(result(),snippet=0)))
        self.assertEqual(state(f,'births'),'UNPARSED')


class Stability(unittest.TestCase):
    def test_inputs_unchanged_and_output_repeatable(self):
        h=make_hit(dobs=['1984','bad date'],countries=['GB','Unrecognisedland'])
        before=copy.deepcopy(h);f=extract(h)
        self.assertEqual(h,before)
        self.assertEqual(json.dumps(f,sort_keys=True),json.dumps(extract(h),sort_keys=True))

    def test_alias_country_birth_and_issue_order_independent(self):
        h=make_hit(aliases=['Zulu Name','Alpha Name'],countries=['US','GB','Bad Country'],dobs=['1984','1985-03','bad date'])
        other=dict(h,aliases=list(reversed(h['aliases'])),countries=list(reversed(h['countries'])),dobs=list(reversed(h['dobs'])))
        self.assertEqual(extract(h),extract(other))


if __name__ == '__main__':
    unittest.main()
