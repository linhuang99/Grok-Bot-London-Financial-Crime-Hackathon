"""Synthetic cross-lane regressions: shared helpers, search keys and quality.

Do not read practice answers or mutate the user's data/worktree.
"""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system'))
from common import dates_agree, parse_date, country_name, field_is_complete
from data import search_keys, find_search_results
from hitfacts import hit_facts
from quality import adapt_person


def hit(name='Example Person', **changes):
    row={'hit_id':'H-ABCDEF','name':name,'entity_type':'Individual','dobs':[],
         'countries':['GB'],'primary_category':'PEP'}
    row.update(changes)
    return row


def row(query, rid='SR-SYNTHETIC', year=1970):
    return {'result_id':rid,'query':query,'title':'Synthetic identity',
            'snippet':'A politically exposed person in United Kingdom, born in %s.' % year}


def person(**changes):
    p={'record_ids':['CUS-000001'],'record_id':'CUS-000001','entity_type':'Individual',
       'verified_name':{'value':'Example Person','source':'SYNTHETIC-CHECK'},
       'names':[{'value':'Example Person','source':'SYNTHETIC-CHECK'}],
       'dob':{'value':(1984,3,14),'source':'SYNTHETIC-CHECK'},
       'countries':[{'value':'United Kingdom','source':'CUS-000001'}],
       'unreadable_countries':[]}
    p.update(changes)
    return p


class SharedCommon(unittest.TestCase):
    def test_lane_a_public_imports_remain_available(self):
        import link
        import customer
        self.assertTrue(callable(link.resolve))
        self.assertTrue(callable(customer.person))
        self.assertTrue(dates_agree((1984,None,None),(1984,3,14)))
        self.assertFalse(dates_agree((1984,3,None),(1984,4,None)))

    def test_lane_a_year_and_placeholder_protections_remain(self):
        self.assertIsNone(parse_date('0099'))
        self.assertIsNone(parse_date('2101'))
        self.assertIsNone(country_name('NA'))
        self.assertIsNone(country_name('N/A'))
        self.assertEqual(country_name('Namibia'),'Namibia')

    def test_lane_b_strict_tuple_validation_remains(self):
        self.assertIsNone(parse_date((1984.5,3,14)))
        self.assertEqual(parse_date((1984,3,14)),(1984,3,14))


class SharedSearch(unittest.TestCase):
    def extract(self,name,query,**changes):
        r=row(query,**changes)
        data={'search_by_query':{search_keys(query)[0]:[r]}}
        self.assertEqual(len(find_search_results(data,name)),1)
        return hit_facts(hit(name),data)

    def test_initials_use_lane_a_keys(self):
        facts=self.extract('Example Q. Person','example person')
        self.assertEqual(facts['births'][0]['value'],(1970,None,None))
        self.assertEqual(facts['birth_source'],'search')

    def test_non_decomposing_letters_use_shared_alternatives(self):
        for query in ['crest pawe','crest pawel']:
            with self.subTest(query=query):
                f=self.extract('Paweł Crest',query)
                self.assertEqual(f['births'][0]['value'],(1970,None,None))

    def test_raw_query_equivalent_to_index_key_is_accepted(self):
        f=self.extract('Example Person','PERSON, Example')
        self.assertEqual(f['quality']['births']['status'],'PARSED')
        self.assertFalse(any(i['code']=='SEARCH_QUERY_MISMATCH' for i in f['issues']))

    def test_conflicts_across_query_variants_are_not_deduplicated_away(self):
        data={'search_by_query':{'crest pawe':[row('crest pawe',year=1970)],
                                 'crest pawel':[row('crest pawel',year=1990)]}}
        f=hit_facts(hit('Paweł Crest'),data)
        self.assertEqual(f['births'],[])
        self.assertIn('UNRESOLVED_SOURCE_CONFLICT',[i['code'] for i in f['issues']])

    def test_unrelated_raw_query_still_rejected(self):
        data={'search_by_query':{'example person':[row('another person')]}}
        f=hit_facts(hit(),data)
        self.assertEqual(f['births'],[])
        self.assertIn('SEARCH_QUERY_MISMATCH',[i['code'] for i in f['issues']])

    def test_unreadable_script_does_not_become_verified_name_mismatch(self):
        f=hit_facts(hit(aliases=['Пример Имя']),{'search_by_query':{}})
        self.assertIn('Пример Имя',f['names'])
        self.assertFalse(field_is_complete(f,'names'))
        self.assertIn('UNREADABLE_NAME_SCRIPT',[i['code'] for i in f['issues']])


class CustomerQualityBridge(unittest.TestCase):
    def test_default_does_not_certify_investigation_coverage(self):
        f=adapt_person(person())
        for field in ['names','births','countries','entity_type']:
            with self.subTest(field=field):
                self.assertFalse(field_is_complete(f,field))
                self.assertEqual(f['quality'][field]['coverage'],'UNKNOWN')

    def test_explicit_complete_field_can_pass_only_its_gate(self):
        f=adapt_person(person(),complete_fields=('countries',))
        self.assertTrue(field_is_complete(f,'countries'))
        self.assertFalse(field_is_complete(f,'births'))

    def test_unreadable_country_blocks_despite_declared_coverage(self):
        p=person(unreadable_countries=[{'value':'Unrecognisedland','source':'CUS-000001'}])
        f=adapt_person(p,complete_fields=('countries',))
        self.assertEqual(f['unreadable_countries'],p['unreadable_countries'])
        self.assertFalse(field_is_complete(f,'countries'))
        self.assertIn('UPSTREAM_UNREADABLE_COUNTRY',[i['code'] for i in f['issues']])

    def test_absent_unreadable_tracking_does_not_count_as_empty(self):
        p=person();p.pop('unreadable_countries')
        f=adapt_person(p,complete_fields=('countries',))
        self.assertFalse(field_is_complete(f,'countries'))

    def test_dob_alias_preserves_original_and_provenance(self):
        p=person();before=copy.deepcopy(p)
        f=adapt_person(p,complete_fields=('births',))
        self.assertEqual(f['dob'],before['dob'])
        self.assertEqual(f['births'],[before['dob']])
        self.assertTrue(field_is_complete(f,'births'))
        self.assertEqual(p,before)
        f['names'][0]['value']='Changed only in copy'
        self.assertEqual(p,before)

    def test_invalid_dob_and_missing_source_are_not_complete(self):
        for dob in [{'value':(99,None,None),'source':'SYNTHETIC-CHECK'},
                    {'value':(1984,None,None)}]:
            with self.subTest(dob=dob):
                f=adapt_person(person(dob=dob),complete_fields=('births',))
                self.assertFalse(field_is_complete(f,'births'))
                self.assertEqual(f['births'],[])

    def test_country_issue_does_not_veto_independent_birth_gate(self):
        f=adapt_person(person(unreadable_countries=[{'value':'?','source':'CUS-000001'}]),
                       complete_fields=('countries','births'))
        self.assertFalse(field_is_complete(f,'countries'))
        self.assertTrue(field_is_complete(f,'births'))

    def test_versions_and_existing_issues_are_not_silently_upgraded(self):
        for version in [1,2]:
            p=person(quality_version=version,quality={},issues=[{'field':'countries','blocking':True}])
            self.assertEqual(adapt_person(p,complete_fields=('countries',)),p)
            self.assertFalse(field_is_complete(adapt_person(p),'countries'))

    def test_malformed_coverage_request_is_a_programming_error(self):
        for fields in ['countries',('unknown_field',)]:
            with self.subTest(fields=fields):
                with self.assertRaises(ValueError):adapt_person(person(),complete_fields=fields)

    def test_bridge_repeatable(self):
        self.assertEqual(adapt_person(person(),complete_fields=('names','births')),
                         adapt_person(person(),complete_fields=('births','names')))


if __name__=='__main__':unittest.main()
