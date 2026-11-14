"""Offline tests; all temporary files stay in this directory."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from merge_scores import load_rubric, merge_scores, render_report

HERE = Path(__file__).resolve().parent
ENV = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.rubric = load_rubric()
        self.a = {'plan': '/plan.md', 'items': [
            {'id': r['id'], 'score': 2, 'na_reason': '', 'evidence': 'L1: 確認', 'gap': ''}
            for r in self.rubric['items']], 'checked': ['file: 確認']}
        self.b = copy.deepcopy(self.a)

    def merge(self, n=1):
        return merge_scores(self.a, self.b, self.rubric, 'J1', 'J2', n)

    def cli(self, directory, *extra):
        for name, data in (('a', self.a), ('b', self.b)):
            (Path(directory) / (name + '.json')).write_text(json.dumps(data), encoding='utf-8')
        return subprocess.run([sys.executable, str(HERE / 'merge_scores.py'),
            '--a', str(Path(directory) / 'a.json'), '--b', str(Path(directory) / 'b.json'),
            '--a-name', 'J1', '--b-name', 'J2', '--round', '1', *extra],
            capture_output=True, text=True, env=ENV)

    def test_real_rubric(self):
        self.assertEqual(len(self.rubric['items']), 12)
        self.assertEqual(sum(r['weight'] for r in self.rubric['items']), 100)

    def test_perfect_receipt(self):
        result = self.merge()
        self.assertEqual(result['total'], 100)
        self.assertTrue(result['pass'])
        expected = '채점 영수증 — 점수 100.0/100 · 합격선 70 · 합격 · 회차 1 · 채점 J1 / J2 · 채점표 v1'
        self.assertEqual(result['receipt'], expected)
        self.assertEqual(render_report(result, 'J1', 'J2').splitlines()[0], expected)
        self.assertEqual(result['gaps'], [])

    def test_lower_score(self):
        self.a['items'][0]['score'] = 1
        result = self.merge()
        self.assertEqual(result['items'][0]['score'], 1)
        self.assertEqual(result['total'], 93)
        self.assertFalse(result['items'][0]['divided'])

    def test_missing_text_fields_are_empty(self):
        for item in self.a['items']:
            del item['na_reason'], item['gap']
        result = self.merge()
        self.assertEqual(result['total'], 100)
        self.assertEqual(result['warnings'], [])

    def test_zero_two_divided(self):
        self.b['items'][0]['score'] = 0
        result = self.merge()
        self.assertTrue(result['items'][0]['divided'])
        self.assertIn('크게 갈림', render_report(result, 'J1', 'J2'))

    def test_null_numeric(self):
        for data in (self.a, self.b):
            data['items'][7]['na_reason'] = '켜야 할 것이 없는 기획이다'
        for number in (0, 1, 2):
            for side in ('a', 'b'):
                with self.subTest(number=number, side=side):
                    self.a['items'][7]['score'] = None if side == 'a' else number
                    self.b['items'][7]['score'] = None if side == 'b' else number
                    result = self.merge()
                    self.assertEqual(result['items'][7]['score'], number)
                    self.assertTrue(result['items'][7]['divided'])

    def test_both_null_excluded(self):
        self.a['items'][7]['score'] = self.b['items'][7]['score'] = None
        for data in (self.a, self.b):
            data['items'][7]['na_reason'] = '켜야 할 것이 없는 기획이다'
        self.a['items'][4]['score'] = 0
        result = self.merge()
        self.assertEqual(result['total'], round(84 / 94 * 100, 1))
        self.assertIsNone(result['items'][7]['score'])
        self.assertNotIn('H', [item['id'] for item in result['gaps']])

    def test_forbidden_null_zero_warning(self):
        self.a['items'][0]['score'] = None
        result = self.merge()
        self.assertEqual(result['items'][0]['score'], 0)
        self.assertTrue(any('J1 A' in w and 'null' in w for w in result['warnings']))

    def test_allowed_null_without_reason_zero_warning(self):
        for reason in (None, '', ' \n '):
            with self.subTest(reason=reason):
                self.a['items'][7]['score'] = None
                if reason is None:
                    self.a['items'][7].pop('na_reason', None)
                else:
                    self.a['items'][7]['na_reason'] = reason
                result = self.merge()
                self.assertEqual(result['items'][7]['a']['score'], 0)
                self.assertEqual(result['items'][7]['score'], 0)
                self.assertEqual(result['warnings'], ['J1 H: 이유 없는 해당 없음 → 0점'])

    def test_allowed_null_with_reason_excluded(self):
        for data in (self.a, self.b):
            data['items'][7].update(score=None, na_reason='켜야 할 것이 없는 기획이다')
        result = self.merge()
        self.assertIsNone(result['items'][7]['score'])
        self.assertEqual(result['total'], 100)
        self.assertNotIn('H', [item['id'] for item in result['gaps']])
        self.assertEqual(result['warnings'], [])

    def test_no_evidence_zero_warning(self):
        for number in (1, 2):
            with self.subTest(number=number):
                self.b['items'][4].update(score=number, evidence=' \n ')
                result = self.merge()
                self.assertEqual(result['items'][4]['score'], 0)
                self.assertTrue(any('J2 E' in w and '근거' in w for w in result['warnings']))

    def test_required_zero_high_total(self):
        self.a['items'][0]['score'] = 0
        result = self.merge()
        self.assertEqual(result['total'], 86)
        self.assertFalse(result['pass'])
        self.assertEqual(result['required_zero'], ['A'])
        self.assertIn('미달(필수 0점: A)', result['receipt'])

    def test_threshold(self):
        for loss, total, passed in ((30.1, 69.9, False), (30, 70.0, True)):
            with self.subTest(total=total):
                self.rubric['items'] = [
                    {'id': 'X', 'weight': 100 - loss, 'required': True, 'na_ok': False},
                    {'id': 'Y', 'weight': loss, 'required': False, 'na_ok': False}]
                self.a['items'] = [dict(self.a['items'][0], id='X', score=2),
                                   dict(self.a['items'][0], id='Y', score=0)]
                self.b = copy.deepcopy(self.a)
                result = self.merge()
                self.assertEqual(result['total'], total)
                self.assertEqual(result['pass'], passed)
                if not passed:
                    self.assertIn('미달(합계 미달)', result['receipt'])

    def test_gaps_order_and_details(self):
        for i in (0, 2, 3):
            self.a['items'][i].update(score=0, gap='더 쓸 것', evidence='찾은 것')
            self.b['items'][i].update(gap='둘째 빈 곳', evidence='L2: 인용')
        result = self.merge()
        self.assertEqual([i['id'] for i in result['gaps']], ['A', 'D', 'C'])
        report = render_report(result, 'J1', 'J2')
        for text in ('더 쓸 것', '찾은 것', '둘째 빈 곳', 'L2: 인용'):
            self.assertIn(text, report)
        self.assertIn('필수 0점: A,C,D', result['receipt'])

    def test_round_limit(self):
        self.assertEqual(self.merge(4)['warnings'], [])
        self.assertIn('재채점 한도 넘음 — [막힘]으로 올릴 것', self.merge(5)['warnings'])

    def test_all_na_error(self):
        for rule in self.rubric['items']:
            rule['na_ok'] = True
        for data in (self.a, self.b):
            for item in data['items']:
                item['score'] = None
                item['na_reason'] = '해당 항목이 없는 기획이다'
        with self.assertRaisesRegex(ValueError, '0개'):
            self.merge()

    def test_cli_missing_duplicate_extra_id(self):
        original = copy.deepcopy(self.a)
        mutations = [lambda items: items.pop(), lambda items: items.append(copy.deepcopy(items[0])),
                     lambda items: items[0].update(id='unknown')]
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for mutate in mutations:
                self.a = copy.deepcopy(original)
                mutate(self.a['items'])
                completed = self.cli(directory)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn('id', completed.stderr)

    def test_cli_invalid_scores(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for invalid in (True, False, 1.0, -1, 3, '2'):
                self.a['items'][0]['score'] = invalid
                completed = self.cli(directory)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn('score', completed.stderr)

    def test_cli_outputs_exit_codes(self):
        with tempfile.TemporaryDirectory(dir=HERE, prefix='spaces here ') as directory:
            report, merged = Path(directory) / 'report.md', Path(directory) / 'merged.json'
            completed = self.cli(directory, '--out', str(report), '--json-out', str(merged))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(merged.read_text(encoding='utf-8'))
            self.assertTrue(result['pass'])
            self.assertEqual(report.read_text(encoding='utf-8').splitlines()[0], result['receipt'])
            self.assertEqual(completed.stdout, '')
            self.a['items'][0]['score'] = 0
            completed = self.cli(directory)
            self.assertEqual(completed.returncode, 1)
            self.assertTrue(completed.stdout.startswith('채점 영수증 —'))

    def test_first_canonical_fence(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            path = Path(directory) / 'rubric.md'
            canonical = json.dumps(self.rubric)
            path.write_text('```json\n{}\n```\n## 기계 정본\n\n```json\n' + canonical
                            + '\n```\n```json\n{}\n```\n', encoding='utf-8')
            self.assertEqual(load_rubric(path), self.rubric)
            path.write_text('## 다른 절\n```json\n' + canonical + '\n```\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '기계 정본'):
                load_rubric(path)

    def test_prompt_and_missing_file(self):
        with tempfile.TemporaryDirectory(dir=HERE, prefix='prompt space ') as directory:
            plan = Path(directory) / 'plan.md'
            plan.write_text('기획', encoding='utf-8')
            command = [sys.executable, str(HERE / 'build_prompt.py'), str(plan)]
            completed = subprocess.run(command, capture_output=True, text=True, env=ENV)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(str(plan), completed.stdout)
            self.assertTrue(completed.stdout.endswith((HERE / 'rubric.md').read_text(encoding='utf-8')))
            repeated = subprocess.run(command, capture_output=True, text=True, env=ENV)
            self.assertEqual(repeated.stdout, completed.stdout)
            plan.unlink()
            completed = subprocess.run(command, capture_output=True, text=True, env=ENV)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, '')

    def test_schema_only_no_model_call(self):
        with tempfile.TemporaryDirectory(dir=HERE, prefix='schema space ') as directory:
            trap = Path(directory) / 'codex'
            marker = Path(directory) / 'called'
            trap.write_text('#!/bin/sh\necho called > "' + str(marker) + '"\nexit 99\n', encoding='utf-8')
            trap.chmod(0o755)
            env = {**ENV, 'PATH': directory + os.pathsep + ENV['PATH']}
            output = Path(directory) / 'output dir'
            completed = subprocess.run(['bash', str(HERE / 'score_openai.sh'), '--schema-only', str(output)],
                                       capture_output=True, text=True, env=env)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual([p.name for p in output.iterdir()], ['score.schema.json'])
            schema = json.loads((output / 'score.schema.json').read_text(encoding='utf-8'))
            def check(node):
                if isinstance(node, dict):
                    if node.get('type') == 'object':
                        self.assertIs(node.get('additionalProperties'), False)
                        self.assertEqual(set(node['properties']), set(node['required']))
                    for value in node.values():
                        check(value)
                elif isinstance(node, list):
                    for value in node:
                        check(value)
            check(schema)
            items = schema['properties']['items']
            self.assertEqual(items['minItems'], len(self.rubric['items']))
            self.assertEqual(items['maxItems'], len(self.rubric['items']))
            props = items['items']['properties']
            self.assertEqual(props['id']['enum'], [i['id'] for i in self.rubric['items']])
            self.assertEqual(props['score'], {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 2})
            self.assertEqual(schema['properties']['checked'], {'type': 'array', 'items': {'type': 'string'}})


if __name__ == '__main__':
    unittest.main()
