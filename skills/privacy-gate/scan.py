#!/usr/bin/env python3
"""Read local files and report only locations and categories, never matched values."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

MAX_BYTES = 1024 * 1024
EXCLUDED = {'.git', 'node_modules'}
BLOCK_KINDS = {'private_key', 'aws_key', 'github_token', 'slack_token',
               'sk_key', 'assignment', 'env_file'}
PATTERNS = [
    ('private_key', re.compile(r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----')),
    ('aws_key', re.compile(r'\bAKIA[A-Z0-9]{16}\b')),
    ('github_token', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)')),
    ('slack_token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]+')),
    ('sk_key', re.compile(r'\bsk-[A-Za-z0-9_-]{8,}')),
    ('assignment', re.compile(
        r'''\b(?:api_key|secret|token|password)\b["']?\s*=\s*(?:"[^"\r\n]{8,}"|'[^'\r\n]{8,}')''',
        re.IGNORECASE)),
    ('phone', re.compile(r'(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)')),
    ('email', re.compile(r'(?<![A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-])[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b')),
    ('resident_id', re.compile(r'(?<!\d)\d{6}-[1-4]\d{6}(?!\d)')),
]


class ScanError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo arguments: they may themselves contain secrets.
        raise ScanError()


def changed_files():
    def git(*args):
        result = subprocess.run(['git', *args], cwd=base, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False)
        if result.returncode:
            raise ScanError()
        return [os.fsdecode(item) for item in result.stdout.split(b'\0') if item]

    root = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if root.returncode:
        raise ScanError()
    base = Path(os.fsdecode(root.stdout).rstrip('\n'))
    names = git('diff', '--name-only', '-z', 'HEAD')
    names += git('ls-files', '--others', '--exclude-standard', '-z')
    return [base / name for name in names if os.path.lexists(base / name)]


def scan(paths):
    result = {'files_scanned': 0, 'skipped': 0, 'findings': [], 'verdict': 'ALLOW'}
    seen = set()

    def finding(path, line, kind):
        result['findings'].append({'file': os.path.relpath(path), 'line': line, 'kind': kind})

    def visit(path):
        path = Path(os.path.abspath(path))
        if path in seen:
            return
        seen.add(path)
        # Check every ancestor, including explicitly supplied excluded paths.
        if EXCLUDED.intersection(path.parts) or any(p.is_symlink() for p in (path, *path.parents)):
            result['skipped'] += 1
            return
        info = path.stat()
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)
            return
        if not stat.S_ISREG(info.st_mode):
            result['skipped'] += 1
            return
        name = path.name.lower()
        if name == '.env' or name.startswith('.env.'):
            finding(path, 1, 'env_file')
        if any(word in name for word in ('credential', 'secret', 'dump', 'backup')):
            finding(path, 1, 'risky_name')
        if info.st_size > MAX_BYTES:
            result['skipped'] += 1
            return
        with path.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or b'\0' in data:
            result['skipped'] += 1
            return
        result['files_scanned'] += 1
        for number, line in enumerate(data.decode('utf-8', errors='replace').splitlines(), 1):
            for kind, pattern in PATTERNS:
                if pattern.search(line):
                    finding(path, number, kind)

    for path in paths:
        visit(path)
    if any(item['kind'] in BLOCK_KINDS for item in result['findings']):
        result['verdict'] = 'BLOCK'
    elif result['findings']:
        result['verdict'] = 'REDACT'
    return result


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('paths', nargs='*')
        parser.add_argument('--diff', action='store_true')
        args = parser.parse_args(argv)
        if args.diff == bool(args.paths):
            raise ScanError()
        result = scan(changed_files() if args.diff else args.paths)
    except (ScanError, OSError, ValueError):
        # A failed run is never an ALLOW. Keep stdout one JSON object even on errors.
        result = {'files_scanned': 0, 'skipped': 0, 'findings': [], 'verdict': 'BLOCK'}
        print(json.dumps(result, ensure_ascii=True))
        print('검사를 끝내지 못했습니다. 인자·경로·읽기 권한·Git 상태를 확인하세요.', file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=True))
    return {'ALLOW': 0, 'REDACT': 1, 'BLOCK': 2}[result['verdict']]


if __name__ == '__main__':
    sys.exit(main())
