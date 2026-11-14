#!/usr/bin/env python3
"""Validate and merge two independent rubric scores."""
import argparse
import json
import math
from pathlib import Path
import re
import sys

DEFAULT_RUBRIC = Path(__file__).with_name('rubric.md')


def load_rubric(path=DEFAULT_RUBRIC):
    text = Path(path).read_text(encoding='utf-8')
    section = re.search(r'^## 기계 정본\s*$', text, re.MULTILINE)
    if not section:
        raise ValueError('rubric: 기계 정본 절이 없습니다')
    body = re.split(r'^## ', text[section.end():], maxsplit=1, flags=re.MULTILINE)[0]
    fence = re.search(r'^```json\s*\n(.*?)^```\s*$', body, re.MULTILINE | re.DOTALL)
    if not fence:
        raise ValueError('rubric: 기계 정본 JSON 울타리가 없습니다')
    rubric = json.loads(fence.group(1))
    if not isinstance(rubric, dict) or not all(
        key in rubric for key in ('version', 'pass_total', 'max_rescore', 'items')
    ):
        raise ValueError('rubric: 필수 속성이 없습니다')
    items = rubric['items']
    if not isinstance(items, list) or not items:
        raise ValueError('rubric: items는 비어 있지 않은 배열이어야 합니다')
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            raise ValueError('rubric: 잘못된 항목 id')
        if item['id'] in ids:
            raise ValueError('rubric: 중복 id')
        ids.add(item['id'])
        weight = item.get('weight')
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight <= 0:
            raise ValueError('rubric: 배점은 양수여야 합니다')
        if any(type(item.get(key)) is not bool for key in ('required', 'na_ok')):
            raise ValueError('rubric: required/na_ok는 boolean이어야 합니다')
    threshold = rubric['pass_total']
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError('rubric: 잘못된 pass_total')
    if type(rubric['max_rescore']) is not int or rubric['max_rescore'] < 0:
        raise ValueError('rubric: 잘못된 max_rescore')
    return rubric


def validate_scores(data, rubric, name, warnings):
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError(f'{name}: items 배열이 필요합니다')
    by_id = {}
    expected = {item['id'] for item in rubric['items']}
    for item in data['items']:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            raise ValueError(f'{name}: 잘못된 항목 id')
        key = item['id']
        if key in by_id:
            raise ValueError(f'{name}: 중복 id {key}')
        if 'score' not in item or (item['score'] is not None and (
            type(item['score']) is not int or item['score'] not in (0, 1, 2)
        )):
            raise ValueError(f'{name}: {key} score는 0,1,2 또는 null이어야 합니다')
        for field in ('na_reason', 'evidence', 'gap'):
            # Judges often omit the optional text fields; missing means empty.
            item.setdefault(field, '')
            if not isinstance(item[field], str):
                raise ValueError(f'{name}: {key} {field} 문자열이 필요합니다')
        by_id[key] = dict(item)
    if set(by_id) != expected:
        raise ValueError(f'{name}: rubric과 id 집합이 다릅니다 (누락={sorted(expected - set(by_id))}, 추가={sorted(set(by_id) - expected)})')
    for rule in rubric['items']:
        item = by_id[rule['id']]
        reason = None
        if item['score'] is None and not rule['na_ok']:
            reason = '해당 없음 불가 항목의 null'
        elif item['score'] is None and not item['na_reason'].strip():
            reason = '이유 없는 해당 없음'
        elif item['score'] in (1, 2) and not item['evidence'].strip():
            reason = '근거 없는 점수'
        if reason:
            item['score'] = 0
            warnings.append(f"{name} {rule['id']}: {reason} → 0점")
    return by_id


def merge_scores(a, b, rubric, a_name, b_name, round_number):
    warnings = []
    a = validate_scores(a, rubric, a_name, warnings)
    b = validate_scores(b, rubric, b_name, warnings)
    items = []
    for rule in rubric['items']:
        key = rule['id']
        x, y = a[key]['score'], b[key]['score']
        numeric = [value for value in (x, y) if value is not None]
        score = min(numeric) if numeric else None
        divided = (x is None) != (y is None) or (x is not None and y is not None and abs(x - y) == 2)
        items.append({**rule, 'a': a[key], 'b': b[key], 'score': score,
                      'divided': divided,
                      'lost': rule['weight'] * (2 - score) / 2 if score is not None else 0})
    applicable = [item for item in items if item['score'] is not None]
    if not applicable:
        raise ValueError('해당 항목이 0개입니다')
    total = round(sum(item['weight'] * item['score'] / 2 for item in applicable)
                  / sum(item['weight'] for item in applicable) * 100, 1)
    required_zero = [item['id'] for item in items if item['required'] and item['score'] == 0]
    reasons = []
    if total < rubric['pass_total']:
        reasons.append('합계 미달')
    if required_zero:
        reasons.append('필수 0점: ' + ','.join(required_zero))
    passed = not reasons
    verdict = '합격' if passed else '미달(' + ', '.join(reasons) + ')'
    receipt = (f"채점 영수증 — 점수 {total}/100 · 합격선 {rubric['pass_total']} · {verdict}"
               f" · 회차 {round_number} · 채점 {a_name} / {b_name} · 채점표 v{rubric['version']}")
    if round_number > rubric['max_rescore'] + 1:
        warnings.append('재채점 한도 넘음 — [막힘]으로 올릴 것')
    gaps = sorted((item for item in applicable if item['score'] < 2), key=lambda item: (-item['lost'], item['id']))
    return {'total': total, 'pass': passed, 'required_zero': required_zero,
            'items': items, 'gaps': gaps, 'receipt': receipt, 'warnings': warnings}


def cell(value):
    return str(value).replace('|', '\\|').replace('\r', ' ').replace('\n', '<br>')


def render_report(result, a_name, b_name):
    lines = [result['receipt'], '', '| id | 배점 | ' + cell(a_name) + ' | ' + cell(b_name) + ' | 합친 점수 | 갈림 |',
             '|---|---:|---:|---:|---:|---|']
    for item in result['items']:
        values = [item['id'], item['weight'], item['a']['score'], item['b']['score'], item['score'],
                  '크게 갈림' if item['divided'] else '']
        lines.append('| ' + ' | '.join('해당 없음' if value is None else cell(value) for value in values) + ' |')
    lines += ['', '## 빈 곳 목록', '']
    for item in result['gaps']:
        lines.append(f"- {cell(item['id'])} (잃은 점수 {item['lost']:g})")
        for side, name in (('a', a_name), ('b', b_name)):
            lines.append(f"  - {cell(name)}: gap={cell(item[side]['gap'])} · evidence={cell(item[side]['evidence'])}")
    if not result['gaps']:
        lines.append('없음')
    lines += ['', '## 경고', '']
    lines.extend('- ' + cell(warning) for warning in result['warnings'])
    if not result['warnings']:
        lines.append('없음')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('a', 'b', 'a-name', 'b-name'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--round', required=True, type=int, dest='round_number')
    parser.add_argument('--rubric', type=Path, default=DEFAULT_RUBRIC)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--json-out', type=Path)
    args = parser.parse_args()
    try:
        if args.round_number < 1:
            raise ValueError('회차는 1 이상이어야 합니다')
        rubric = load_rubric(args.rubric)
        inputs = [json.loads(Path(path).read_text(encoding='utf-8')) for path in (args.a, args.b)]
        result = merge_scores(*inputs, rubric, args.a_name, args.b_name, args.round_number)
        report = render_report(result, args.a_name, args.b_name)
        if args.out:
            args.out.write_text(report, encoding='utf-8')
        else:
            print(report, end='')
        if args.json_out:
            args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return 0 if result['pass'] else 1
    except (OSError, ValueError, TypeError) as exc:
        print(f'입력 오류: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
