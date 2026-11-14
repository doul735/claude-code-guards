#!/usr/bin/env python3
"""실행 시점의 양사 모델을 급(tier)별로 찾는다. 모델명을 코드에 박지 않는다.

사용: resolve_top_models.py [--tier top|mid]   (기본 top)

정본 = 모델 대응표 파일(기본 ~/.claude/model-tiers.md, 환경변수 MODEL_TIERS_FILE 로 바꿈). 급→모델 대응은 이 표만 갱신한다.
  top: Claude "최상위" 행 + OpenAI "최상위" 행
  mid: Claude "상위"(최상위 아님) 행 + OpenAI "주력" 행
- Claude: 대응 칸의 첫 단어를 소문자로 → Agent 도구 별칭(예: 칸이 "Opus ..." 로 시작하면 opus).
- OpenAI: 대응 칸의 gpt-… 슬러그. ~/.codex/models_cache.json 에서 visibility=list·supported_in_api·은퇴 예정(upgrade) 아님인지 검증한다.
  표에는 있는데 캐시에 없으면 ok=false (표가 낡았거나 CLI 캐시가 낡은 것 — 어느 쪽인지는 사람이 본다).
- 표 파일이 없을 때(top만): OpenAI는 위 필터를 통과한 모델의 description을 소문자로 비교해 OPENAI_TOP_MARKERS 중 하나가 있는 모델을 고른다.
  여러 개면 그중 priority 최소, 일치가 없으면 ok=false(후보 수 포함). 결과에 matched_marker와 source=cache-fallback 표시.
  priority는 표시 순서지 서열이 아니다(최상위가 아닌 모델을 잘못 고른 적이 있다).
  Claude는 description에 'Most capable'이 있는 모델을 고른다.
  mid는 표 없이는 못 고른다(캐시엔 서열이 없다) → ok=false.
추론 강도: 변수 ASK_TOP_EFFORT(기본 medium). OpenAI는 그 모델 지원 목록, Claude는 Agent가 받는 값 목록(low~max)에서 따로 판정.
출력: JSON 한 줄. 찾지 못한 쪽은 ok=false와 이유. exit 2 = 한쪽이라도 못 찾음 (몰래 대체하지 않는다).
"""
import json, os, re, sys, ast, argparse

OPENAI_TOP_MARKERS = ["frontier", "most capable", "most demanding"]

home = os.path.expanduser("~")
ap = argparse.ArgumentParser()
ap.add_argument("--tier", choices=["top", "mid"], default="top")
tier = ap.parse_args().tier
out = {"tier": tier}
want = os.environ.get("ASK_TOP_EFFORT", "medium")
CLAUDE_LEVELS = ["low", "medium", "high", "xhigh", "max"]

def read_table():
    p = os.environ.get("MODEL_TIERS_FILE") or os.path.join(home, ".claude/model-tiers.md")
    if not os.path.exists(p):
        return None
    rows = {}
    for line in open(p, encoding="utf-8"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and not cells[0].startswith("-") and cells[0] != "급":
            rows[cells[0]] = cells[1]
    return rows

def pick_row(rows, vendor, tier):
    if tier == "top":
        pat = {"claude": r"^Claude.*최상위", "openai": r"^OpenAI.*최상위"}[vendor]
    else:
        pat = {"claude": r"^Claude\s*상위", "openai": r"^OpenAI.*주력"}[vendor]
    hits = [(k, v) for k, v in rows.items() if re.search(pat, k)]
    if len(hits) != 1:
        raise ValueError(f"표에서 {vendor}/{tier} 행 {len(hits)}개 (정확히 1개여야 함)")
    return hits[0]

cache = None
try:
    cache = json.load(open(os.path.join(home, ".codex/models_cache.json")))
except Exception as e:
    cache_err = f"{type(e).__name__}: {e}"

def openai_from_cache(slug=None):
    # supported_in_api 유지(Codex P2, PR #60): API 키 세션은 picker에 보여도 API 미지원 모델이면 codex exec에서야 실패한다.
    ms = [m for m in cache.get("models", [])
          if m.get("visibility") == "list" and m.get("supported_in_api") and not m.get("upgrade")]
    if slug:
        ms = [m for m in ms if m.get("slug") == slug]
        if not ms:
            raise ValueError(f"표의 {slug} 가 codex 모델 캐시(list·API 지원·비은퇴)에 없음")
        m = ms[0]
    else:
        candidates = [m for m in ms if any(marker in (m.get("description") or "").lower()
                                          for marker in OPENAI_TOP_MARKERS)]
        if not candidates:
            raise ValueError(f"최상위 표지어 일치 모델 없음, 후보 {len(ms)}개")
        m = min(candidates, key=lambda m: m.get("priority", 1e9))
    matched_marker = next((marker for marker in OPENAI_TOP_MARKERS
                           if marker in (m.get("description") or "").lower()), None)
    levels = m.get("supported_reasoning_levels") or []
    if isinstance(levels, str):
        levels = ast.literal_eval(levels)
    supported = [l["effort"] for l in levels]
    effort = want if want in supported else (supported[(len(supported) - 1) // 2] if supported else None)
    return {"ok": True, "model": m["slug"], "display": m.get("display_name"), "description": m.get("description"),
            "matched_marker": matched_marker,
            "effort": effort, "effort_requested": want, "effort_supported": supported,
            "priority": m.get("priority"), "cache_fetched_at": cache.get("fetched_at")}

rows = read_table()
ceffort = want if want in CLAUDE_LEVELS else CLAUDE_LEVELS[(len(CLAUDE_LEVELS) - 1) // 2]

try:
    if rows is None:
        if tier != "top":
            raise ValueError("모델 대응표 파일 없음 — mid 급은 표 없이 못 고름")
        if cache is None:
            raise ValueError(cache_err)
        out["openai"] = openai_from_cache() | {"source": "cache-fallback"}
    else:
        k, v = pick_row(rows, "openai", tier)
        m = re.search(r"gpt-[\w.\-]+", v)
        if not m:
            raise ValueError(f"표 행 '{k}' 에서 gpt- 슬러그를 못 찾음: {v}")
        if cache is None:
            raise ValueError(cache_err)
        out["openai"] = openai_from_cache(m.group(0)) | {"source": "model-tiers", "row": k}
except Exception as e:
    out["openai"] = {"ok": False, "reason": f"{type(e).__name__}: {e}"}

try:
    if rows is None:
        if tier != "top":
            raise ValueError("모델 대응표 파일 없음 — mid 급은 표 없이 못 고름")
        c = json.load(open(os.path.join(home, ".claude.json")))
        opts = c.get("additionalModelOptionsCache") or []
        cand = [o for o in opts if "most capable" in (o.get("description") or "").lower()]
        if not cand:
            raise ValueError(f"'Most capable' 항목 없음 (선택지 {len(opts)}개)")
        o = cand[0]
        out["claude"] = {"ok": True, "agent_alias": (o.get("label") or "").strip().lower(), "effort": ceffort,
                         "model_value": o.get("value"), "description": o.get("description"), "source": "cache-fallback"}
    else:
        k, v = pick_row(rows, "claude", tier)
        alias = re.split(r"[\s(]", v.strip())[0].lower()
        if not alias:
            raise ValueError(f"표 행 '{k}' 대응 칸이 비어 있음")
        out["claude"] = {"ok": True, "agent_alias": alias, "effort": ceffort, "display": v, "source": "model-tiers", "row": k}
except Exception as e:
    out["claude"] = {"ok": False, "reason": f"{type(e).__name__}: {e}"}

print(json.dumps(out, ensure_ascii=False))
sys.exit(0 if out["openai"]["ok"] and out["claude"]["ok"] else 2)
