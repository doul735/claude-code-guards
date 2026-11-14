#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <기획 문서 절대경로> <출력 폴더 절대경로> <모델> <강도>" >&2
    echo "       $0 --schema-only <출력 폴더 절대경로>" >&2
    exit 2
}
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
schema_only=false
if [[ $# -eq 2 && $1 == --schema-only ]]; then
    schema_only=true
    out=$2
elif [[ $# -eq 4 ]]; then
    plan=$1
    out=$2
    model=$3
    effort=$4
    [[ $plan == /* ]] || usage
else
    usage
fi
[[ $out == /* ]] || usage
mkdir -p -- "$out"
if [[ $schema_only == false ]]; then
    python3 "$script_dir/build_prompt.py" "$plan" > "$out/openai-prompt.md"
fi
python3 - "$script_dir" "$out/score.schema.json" <<'PY'
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import json
from pathlib import Path
from merge_scores import load_rubric

rubric = load_rubric()
def obj(properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}

schema = obj({
    'plan': {'type': 'string'},
    'items': {'type': 'array', 'minItems': len(rubric['items']),
              'maxItems': len(rubric['items']), 'items': obj({
                  'id': {'type': 'string', 'enum': [item['id'] for item in rubric['items']]},
                  'score': {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 2},
                  'na_reason': {'type': 'string'}, 'evidence': {'type': 'string'},
                  'gap': {'type': 'string'}})},
    'checked': {'type': 'array', 'items': {'type': 'string'}}})
Path(sys.argv[2]).write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
if [[ $schema_only == true ]]; then
    exit 0
fi
# Each invocation has its own output; an earlier result cannot hide a failure.
rm -f -- "$out/openai-score.json" "$out/openai-retry.txt"
run_score() {
    if command -v timeout >/dev/null 2>&1; then
        timeout 580 codex exec -m "$model" -c "model_reasoning_effort=\"$effort\"" -s read-only --skip-git-repo-check --output-schema "$out/score.schema.json" -o "$out/openai-score.json" - < "$out/openai-prompt.md" > "$out/openai-raw.log" 2>&1
    else
        codex exec -m "$model" -c "model_reasoning_effort=\"$effort\"" -s read-only --skip-git-repo-check --output-schema "$out/score.schema.json" -o "$out/openai-score.json" - < "$out/openai-prompt.md" > "$out/openai-raw.log" 2>&1
    fi
}
if run_score; then
    :
else
    status=$?
    previous=$effort
    case $effort in
        xhigh) effort=high ;;
        high) effort=medium ;;
        medium) effort=low ;;
        *) effort=low ;;
    esac
    printf '첫 실행 실패(exit %s), 강도 %s → %s, 1회 재시도\n' "$status" "$previous" "$effort" > "$out/openai-retry.txt"
    # Preserve both attempts in the same raw log.
    first_log=$(cat -- "$out/openai-raw.log")
    rm -f -- "$out/openai-score.json"
    retry_status=0
    run_score || retry_status=$?
    retry_log=$(cat -- "$out/openai-raw.log")
    printf '%s\n\n--- 재시도 ---\n%s\n' "$first_log" "$retry_log" > "$out/openai-raw.log"
    if [[ $retry_status -ne 0 ]]; then
        echo "재시도 실패(exit $retry_status)" >&2
        exit 1
    fi
fi
python3 - "$out/openai-score.json" <<'PY'
import json
import sys
try:
    with open(sys.argv[1], encoding='utf-8') as source:
        json.load(source, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
except (OSError, ValueError) as exc:
    print(f'점수 JSON 오류: {exc}', file=sys.stderr)
    sys.exit(1)
PY
