"""Regression checks for Lane B's AGENTS.md hard rules, synthetic inputs only.

These are guardrails, not a proof of identity-policy correctness. The official
checker must still run after each system change; the current runner is a stub.
"""
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import sysconfig
import unittest

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / 'system'
sys.path.insert(0, str(SYSTEM))
from hitfacts import hit_facts
from common import parse_date

LANE_B = ('common.py', 'names.py', 'hitfacts.py')


class HardRules(unittest.TestCase):
    def test_lane_b_imports_are_standard_library_or_local(self):
        local = {p.stem for p in SYSTEM.glob('*.py')}
        for filename in LANE_B:
            tree = ast.parse((SYSTEM / filename).read_text())
            for node in ast.walk(tree):
                modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                for module in modules:
                    root = module.split('.')[0]
                    if root in local:
                        continue
                    spec = importlib.util.find_spec(root)
                    self.assertIsNotNone(spec, (filename, module))
                    origin = str(spec.origin)
                    self.assertTrue(origin in ('built-in', 'frozen') or
                                    (origin.startswith(sysconfig.get_paths()['stdlib']) and
                                     'site-packages' not in origin and 'dist-packages' not in origin),
                                    (filename, module, origin))

    def test_no_network_model_or_random_clock_in_lane_b(self):
        prohibited = {'random', 'time', 'requests', 'openai', 'http', 'urllib', 'socket'}
        for filename in LANE_B:
            tree = ast.parse((SYSTEM / filename).read_text())
            for node in ast.walk(tree):
                modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                self.assertFalse({m.split('.')[0] for m in modules} & prohibited)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, {'now', 'utcnow', 'today'})
        # No model call is implemented. Adding one requires explicit OpenRouter,
        # pinned-model/temperature validation and new tests, not an SDK shortcut.

    def test_no_runtime_practice_paths_or_literal_participant_ids(self):
        for filename in LANE_B:
            tree = ast.parse((SYSTEM / filename).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotIn('practice_labels.jsonl', node.value)
                    self.assertIsNone(re.search(r'\b(?:H-[0-9A-F]{6}|CUS-\d{6}|KYC-[0-9A-F]{6})\b', node.value))
                    self.assertIsNone(re.search(r'(?:sk-or-v1-|xai-)[A-Za-z0-9_-]{12,}',node.value))

    def test_unknown_type_and_birth_stay_unknown(self):
        hit = {'hit_id':'H-ABCDEF', 'profile_notes':'Born in 1984.', 'dobs':[]}
        facts = hit_facts(hit, {})
        self.assertIsNone(facts['entity_type'])
        self.assertEqual(facts['births'], [])
        self.assertEqual(facts['countries'], [])

    def test_english_dates_do_not_depend_on_calendar_locale_names(self):
        import calendar
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('isolated_common', SYSTEM / 'common.py')
        module = importlib.util.module_from_spec(spec)
        with patch.object(calendar, 'month_name', ['locale changed'] * 13), patch.object(calendar, 'month_abbr', ['different'] * 13):
            spec.loader.exec_module(module)
            self.assertEqual(module.parse_date('14 March 1984'), (1984,3,14))
        self.assertIsNone(module.parse_date('1984-02-31'))

    def test_extraction_does_not_mutate_input(self):
        hit = {'hit_id':'H-ABCDEF','name':'Example Person','aliases':['Sample Name'],
               'entity_type':'Individual','dobs':['1984'],'countries':['GB']}
        before = json.dumps(hit, sort_keys=True)
        hit_facts(hit, {})
        self.assertEqual(before, json.dumps(hit, sort_keys=True))

    def test_alias_order_does_not_change_output(self):
        hit = {'hit_id':'H-ABCDEF','name':'Example Person','aliases':['Zulu Name','Alpha Name'],
               'entity_type':'Individual','dobs':['1984'],'countries':['GB','US']}
        first = hit_facts(hit, {})
        second = hit_facts(dict(hit, aliases=list(reversed(hit['aliases'])),
                                countries=list(reversed(hit['countries']))), {})
        self.assertEqual(first, second)

    def test_different_hash_seeds_and_working_directories(self):
        script = '''import sys,json
sys.path.insert(0, sys.argv[1])
from hitfacts import hit_facts
hit={'hit_id':'H-ABCDEF','name':'Example Person','aliases':['Sample Name'],
     'entity_type':'Individual','dobs':['1984','1985-03'],
     'countries':['GB','US'],'profile_notes':'No extra facts.'}
print(json.dumps(hit_facts(hit,{}),sort_keys=True))
'''
        outputs=[]
        for seed, cwd in [('1',ROOT), ('321',SYSTEM)]:
            env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONDONTWRITEBYTECODE='1')
            outputs.append(subprocess.check_output([sys.executable,'-c',script,str(SYSTEM)],cwd=cwd,env=env,text=True))
        self.assertEqual(*outputs)


if __name__ == '__main__':
    unittest.main()
