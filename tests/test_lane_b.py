"""Synthetic fixtures only: no participant records or practice answers."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system'))
from common import parse_date, country_name, country_at_end, countries_in_text, search_query
from names import names_agree, company_names_agree, name_parts, usable_individual_name
from hitfacts import hit_facts

VARIANTS = {'groups': [['robert', 'bob'], ['mohammed', 'muhammad']],
            'company_legal_forms': ['ltd', 'limited', 'ab', 'sa']}


class Dates(unittest.TestCase):
    def test_partial(self):
        for s, expected in [('1984', (1984,None,None)), ('1984-02',(1984,2,None)),
                            ('February 1984',(1984,2,None)), ('1984-02-29',(1984,2,29))]:
            with self.subTest(s=s): self.assertEqual(parse_date(s), expected)
    def test_written(self):
        for s in ['29/02/1984', '29 February 1984', 'February 29, 1984', '29 Feb 1984', 'Feb 29 1984']:
            with self.subTest(s=s): self.assertEqual(parse_date(s), (1984,2,29))
    def test_invalid(self):
        for s in [None,'','unknown','1983-02-29','1984-13','01/02/84',(1984,None,2)]:
            with self.subTest(s=s): self.assertIsNone(parse_date(s))


class Countries(unittest.TestCase):
    def test_aliases(self):
        for s in ['GB','UK','British','United Kingdom']:
            self.assertEqual(country_name(s),'United Kingdom')
        self.assertEqual(country_name('US'),'United States')
        self.assertEqual(country_name('United States [Associated]'),'United States')
        self.assertEqual(country_name('Kosovo'),'Kosovo')
        self.assertEqual(country_name('Russian'),'Russia')
        self.assertEqual(country_name('United States [Associated]'),'United States')
        self.assertEqual(country_name('Macao Special Administrative Region of China'),'Macao')
        self.assertEqual(country_name('Trinidad and Tobago'),'Trinidad and Tobago')
    def test_unknown(self):
        for s in ['Europe','International','Atlantis',None,'London']:
            self.assertIsNone(country_name(s))
    def test_territory_and_address(self):
        self.assertNotEqual(country_name('HK'),country_name('CN'))
        self.assertEqual(country_at_end('Example City, GB'),'United Kingdom')
    def test_prose_boundaries(self):
        self.assertIn('Nigeria',countries_in_text('A Nigerian official.'))
        self.assertNotIn('United States',countries_in_text('A Russian official.'))
        self.assertEqual(countries_in_text('North Korean official.'), {'North Korea'})
        self.assertEqual(countries_in_text('Macao Special Administrative Region of China'), {'Macao'})


class Names(unittest.TestCase):
    def agree(self,a,b): return names_agree(a,b,VARIANTS)
    def test_normalization(self):
        self.assertTrue(self.agree('José A. Silva (archived)', 'Silva Jose'))
        self.assertEqual(name_parts('NA N/A TEST UNKNOWN XXX NONE 123 A. AB123'), ())
        self.assertEqual(name_parts('Rose Rose Tyler'), ('rose','tyler'))
        self.assertFalse(self.agree('UNKNOWN','UNKNOWN'))
    def test_variants_alias_and_order(self):
        self.assertTrue(self.agree('Bob Stone','Robert Stone'))
        self.assertTrue(self.agree('Mohammed Khan','Khan Muhammad'))
        self.assertTrue(self.agree('Bob', 'Robert Stone'))
    def test_edits(self):
        self.assertTrue(self.agree('Marta Zed','Martha Zed'))
        # Single matching part is insufficient when both names have two parts.
        self.assertFalse(self.agree('Marta Zed','Martha Rex'))
    def test_short_exact(self):
        self.assertFalse(self.agree('Li Zed','Lu Rex'))
        self.assertFalse(self.agree('Anne Zed','An Rex'))
    def test_distance_length_and_transposition(self):
        self.assertTrue(self.agree('Martha','Marta'))
        self.assertFalse(self.agree('Marta','Matra'))
        self.assertTrue(self.agree('Jonathan','Jonathen'))
    def test_split_join(self):
        self.assertTrue(self.agree('Abdulsalam Stone','Abdul Salam Stone'))
        self.assertTrue(self.agree('Abdulsalam','Abdul Salam'))
        self.assertFalse(self.agree('Abdulsalam Zed','Abdul Salam Rex'))
    def test_company_scope(self):
        self.assertTrue(company_names_agree('Silver Orchard Ltd','Orchard Silver AB',VARIANTS))
        self.assertFalse(company_names_agree('Orchard Ltd','Mountain Ltd',VARIANTS))
        self.assertIn('sa',name_parts('Sa Stone',VARIANTS))
    def test_customer_gate(self):
        self.assertFalse(usable_individual_name('Bob'))
        self.assertFalse(usable_individual_name('A. TEST Stone'))
        self.assertTrue(usable_individual_name('Robert Stone'))


class HitFacts(unittest.TestCase):
    def hit(self, **kwargs):
        return dict(hit_id='H-ABCDEF', name='Example Person', aliases=[], entity_type='Individual',
                    dobs=[], countries=['GB'], **kwargs)
    def test_structured_precedence(self):
        h=self.hit(profile_notes='Born in 1920.');h['dobs']=['1984']
        f=hit_facts(h,{})
        self.assertEqual(f['births'],[{'value':(1984,None,None),'source':'H-ABCDEF#dobs'}])
    def test_age_uncertainty(self):
        f=hit_facts(self.hit(profile_notes='The individual was aged 45 in March 2019.'),{})
        self.assertEqual({x['value'][0] for x in f['births']},{1973,1974})
    def test_first_paragraph(self):
        h=self.hit(profile_notes='No biographical date.\n\nAnother person was born in 1920.')
        self.assertEqual(hit_facts(h,{})['births'],[])
    def test_company_not_born_from_notes(self):
        h=self.hit(profile_notes='Born in 1920.');h['entity_type']='Company'
        self.assertEqual(hit_facts(h,{})['births'],[])
    def test_report_format(self):
        h=self.hit(profile_notes='Biography.\nAccording to Example News; March 12, 2019: event.\nAccording to Another Source; May 4, 2017: event.\nReported in 1900.')
        self.assertEqual(hit_facts(h,{})['earliest_report']['value'],(2017,5,4))
    def test_invalid_report_not_counted(self):
        self.assertIsNone(hit_facts(self.hit(profile_notes='Reported March 12, 2019: event.'),{})['earliest_report'])
    def test_search_filters(self):
        h=self.hit(primary_category='PEP')
        def row(rid,text):return dict(result_id=rid,title='Example Person',snippet=text)
        rows=[row('SR-OK','A politically exposed person in United Kingdom, born in 1970.'),
              row('SR-WRONG-COUNTRY','A politically exposed person in Nigeria, born in 1980.'),
              row('SR-WRONG-KIND','A musician in United Kingdom, born in 1990.')]
        f=hit_facts(h,{'search_by_query':{search_query(h['name']):rows}})
        self.assertEqual(f['births'],[{'value':(1970,None,None),'source':'SR-OK'}])
    def test_no_search_if_profile_has_birth(self):
        h=self.hit(profile_notes='Born on 14 March 1984.',primary_category='PEP')
        f=hit_facts(h,{'search_by_query':{search_query(h['name']):[dict(result_id='SR-X',title='',snippet='A politically exposed person in United Kingdom, born in 1900.')]}})
        self.assertEqual(f['births'][0]['value'],(1984,3,14))
    def test_country_sources_death_and_determinism(self):
        h=self.hit(addresses=['Example City, Nigeria'],nationality=['British'],place_of_birth='Example City, HK',deceased_date='2020-02-01')
        f=hit_facts(h,{})
        self.assertEqual({x['value'] for x in f['countries']},{'United Kingdom','Nigeria','Hong Kong'})
        self.assertEqual(f['death']['value'],(2020,2,1))
        self.assertEqual(f,hit_facts(h,{}))


if __name__=='__main__':unittest.main()
