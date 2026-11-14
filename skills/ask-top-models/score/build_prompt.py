#!/usr/bin/env python3
"""Build the identical scoring prompt for every judge."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path, help='기획 문서 절대경로')
    args = parser.parse_args()
    if not args.plan.is_absolute() or not args.plan.is_file():
        parser.error('기획 문서의 존재하는 절대경로가 필요합니다')
    rubric = Path(__file__).with_name('rubric.md').read_text(encoding='utf-8')
    header = (
        '너는 채점자다. 아래 채점표를 그대로 따른다.\n'
        f'기획 문서는 {args.plan}에 있다. 직접 열어 줄 번호와 함께 끝까지 읽어라.\n'
        '기획이 가리키는 파일·숫자 하나 이상을 직접 열어 확인하라.\n'
        '답은 채점표 맨 끝 모양의 JSON 하나만 내라. 그 밖의 글은 금지한다.\n'
        '파일을 고치지 마라.\n\n'
    )
    print(header + rubric, end='')


if __name__ == '__main__':
    main()
