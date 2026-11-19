"""Local fixtures are created at runtime and removed after each test."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCANNER = Path(__file__).with_name('scan.py').resolve()


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCANNER.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        return path

    def run_scan(self, *args):
        process = subprocess.run([sys.executable, str(SCANNER), *map(str, args)],
                                 cwd=self.root, capture_output=True, text=True,
                                 env={**os.environ, 'GIT_CEILING_DIRECTORIES': str(self.root.parent)})
        report = json.loads(process.stdout)
        self.assertEqual(set(report), {'files_scanned', 'skipped', 'findings', 'verdict'})
        for item in report['findings']:
            self.assertEqual(set(item), {'file', 'line', 'kind'})
        return process, report

    def test_clean_allow(self):
        process, report = self.run_scan(self.write('clean.txt', 'hello\n'))
        self.assertEqual((process.returncode, report['verdict'], report['files_scanned']), (0, 'ALLOW', 1))
        self.assertEqual(report['findings'], [])

    def test_phone_redact(self):
        process, report = self.run_scan(self.write('contact.txt', '010-' + '0000-0000'))
        self.assertEqual((process.returncode, report['verdict']), (1, 'REDACT'))
        self.assertEqual(report['findings'][0]['kind'], 'phone')

    def test_email_long_base64_finishes_under_one_second(self):
        spec = importlib.util.spec_from_file_location('privacy_scan', SCANNER)
        scanner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scanner)
        pattern = dict(scanner.PATTERNS)['email']
        line = 'Ab0/' * 25000
        started = time.perf_counter()
        match = pattern.search(line)
        elapsed = time.perf_counter() - started
        self.assertIsNone(match)
        self.assertLess(elapsed, 1.0)

    def test_email_with_dot_and_plus(self):
        process, report = self.run_scan(self.write('contact.txt', 'a.b+c@example.com'))
        self.assertEqual((process.returncode, report['verdict']), (1, 'REDACT'))
        self.assertIn('email', [item['kind'] for item in report['findings']])

    def test_assignment_does_not_cross_closing_quote(self):
        for quote in ('"', "'"):
            for value in ('', 'z' * 7):
                with self.subTest(quote=quote, value_length=len(value)):
                    line = 'to' + 'ken = ' + quote + value + quote + ', description = ' + quote + 'public text' + quote
                    process, report = self.run_scan(self.write('config.txt', line))
                    self.assertEqual((process.returncode, report['verdict']), (0, 'ALLOW'))
                    self.assertEqual(report['findings'], [])

    def test_assignment_eight_character_value_blocks(self):
        for quote in ('"', "'"):
            with self.subTest(quote=quote):
                value = 'fake' + 'value'
                line = 'To' + 'KeN = ' + quote + value + quote
                process, report = self.run_scan(self.write('config.txt', line))
                self.assertEqual((process.returncode, report['verdict']), (2, 'BLOCK'))
                self.assertEqual(report['findings'][0]['kind'], 'assignment')
                self.assertNotIn(value, process.stdout + process.stderr)

    def test_aws_block_and_no_values(self):
        value = 'AK' + 'IA' + 'Z' * 16
        process, report = self.run_scan(self.write('config.txt', '\n' + value))
        self.assertEqual((process.returncode, report['verdict']), (2, 'BLOCK'))
        self.assertEqual(report['findings'][0]['line'], 2)
        self.assertNotIn(value, process.stdout + process.stderr)

    def test_env_block(self):
        for name in ('.env', '.env.local'):
            with self.subTest(name=name):
                process, report = self.run_scan(self.write(name, ''))
                self.assertEqual((process.returncode, report['verdict']), (2, 'BLOCK'))
                self.assertEqual(report['findings'][0]['kind'], 'env_file')

    def test_binary_skipped(self):
        process, report = self.run_scan(self.write('image.bin', b'\0' + b'AK' + b'IA' + b'Z' * 16))
        self.assertEqual((process.returncode, report['files_scanned'], report['skipped']), (0, 0, 1))

    def test_other_patterns_and_no_values(self):
        cases = [
            ('private_key', '-----BEGIN ' + 'RSA PRIVATE KEY-----', 2),
            ('github_token', 'gh' + 'p_' + 'z' * 36, 2),
            ('github_token', 'github_' + 'pat_' + 'z' * 30, 2),
            ('slack_token', 'xo' + 'xb-' + '123456789-abcdefgh', 2),
            ('sk_key', 's' + 'k-proj-' + 'z' * 30, 2),
            ('sk_key', 's' + 'k-ant-api03-' + 'z' * 30, 2),
            ('assignment', 'api_' + 'key = "' + 'z' * 12 + '"', 2),
            ('assignment', 'PASS' + "WORD = '" + 'z' * 12 + "'", 2),
            ('email', 'someone' + '@example.com', 1),
            ('resident_id', '900101-' + '1234567', 1),
        ]
        for kind, value, code in cases:
            with self.subTest(kind=kind, value_length=len(value)):
                process, report = self.run_scan(self.write('sample.txt', value))
                self.assertEqual(process.returncode, code)
                self.assertIn(kind, [item['kind'] for item in report['findings']])
                self.assertNotIn(value, process.stdout + process.stderr)

    def test_recursive_exclusions_large_and_duplicates(self):
        self.write('nested/clean.txt', 'hello')
        self.write('.git/hidden', 'hello')
        self.write('node_modules/hidden', 'hello')
        self.write('large.txt', b'a' * (1024 * 1024 + 1))
        process, report = self.run_scan(self.root, self.root / 'nested/clean.txt')
        self.assertEqual((process.returncode, report['files_scanned'], report['skipped']), (0, 1, 3))

    def test_risky_name(self):
        process, report = self.run_scan(self.write('backup.txt', 'hello'))
        self.assertEqual((process.returncode, report['verdict']), (1, 'REDACT'))
        self.assertEqual(report['findings'][0]['kind'], 'risky_name')

    def test_symlink_skipped(self):
        path = self.write('clean.txt', 'hello')
        (self.root / 'link').symlink_to(path)
        process, report = self.run_scan(self.root / 'link')
        self.assertEqual((process.returncode, report['skipped']), (0, 1))

    def test_errors_are_not_allow(self):
        for args in ((), ('missing.txt',), ('--diff', '.'), ('--unknown',), ('--diff',)):
            with self.subTest(args=args):
                process, report = self.run_scan(*args)
                self.assertEqual((process.returncode, report['verdict']), (3, 'BLOCK'))

    def test_diff_paths_and_deleted_files(self):
        spec = importlib.util.spec_from_file_location('privacy_scan', SCANNER)
        scanner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scanner)
        tracked = self.write('tracked.txt', 'hello')
        untracked = self.write('untracked contact.txt', 'hello')
        responses = [
            subprocess.CompletedProcess([], 0, os.fsencode(self.root) + b'\n'),
            subprocess.CompletedProcess([], 0, b'tracked.txt\0deleted.txt\0'),
            subprocess.CompletedProcess([], 0, b'untracked contact.txt\0'),
        ]
        with mock.patch.object(scanner.subprocess, 'run', side_effect=responses) as run:
            self.assertEqual(scanner.changed_files(), [tracked, untracked])
        self.assertEqual(run.call_args_list[1].kwargs['cwd'], self.root)
        self.assertEqual(run.call_args_list[2].kwargs['cwd'], self.root)
        self.assertEqual(run.call_args_list[1].args[0],
                         ['git', 'diff', '--name-only', '-z', 'HEAD'])
        self.assertEqual(run.call_args_list[2].args[0],
                         ['git', 'ls-files', '--others', '--exclude-standard', '-z'])


if __name__ == '__main__':
    unittest.main()
