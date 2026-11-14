---
name: ask-top-models
description: 설계·방향·규칙안을 사용자에게 묻기 전에, 서로 다른 두 모델(Claude + codex·gemini CLI 또는 OpenRouter의 무료·저가 모델, 구독이 없으면 서브에이전트 둘)에게 각자 독립 의견과 반박을 받아 종합한다. 모델명은 하드코딩하지 않고 실행할 때 찾는다. 사용자가 "나한테 묻지 말고 최상위 모델들한테 물어봐", "최상위 모델들 의견 받아", "/ask-top-models"라고 할 때, 또는 사업 판단이 아닌 설계 판단을 사용자에게 올리려 할 때 사용.
---

# ask-top-models — 서로 다른 두 모델의 교차 의견

## 시작 구성 — 구독이 하나뿐이어도 된다

둘째 목소리를 어디서 가져올지 고른다. `ask.workflow.js`의 `secondBackend` 인자다.

| 둘째 목소리 | `secondBackend` | 필요한 것 |
|---|---|---|
| OpenRouter의 모델 하나 (무료 모델 가능) | `openrouter` | 환경변수 `OPENROUTER_API_KEY`, 모델 이름(`secondModel` 또는 `OPENROUTER_MODEL`) |
| codex CLI가 있을 때 | `codex` (기본) | 로그인된 `codex` |
| gemini CLI가 있을 때 | `gemini` | 로그인된 `gemini` |
| 아무것도 없을 때 | `subagent` | Claude Code만. 같은 Claude 안에서 반대 입장으로 읽는 두 번째 서브에이전트 |

**최소 구성은 Claude Code 하나와 OpenRouter 무료 키 하나다.** 키 값은 환경변수로만 넘기고 어떤 파일에도 적지 않는다. 모델 이름은 코드에 박지 않는다 — openrouter.ai/models 에서 지금 쓸 수 있는 이름을 찾아 쓴다(무료 모델은 이름 끝에 `:free`가 붙는다). 예: `export OPENROUTER_API_KEY=<키>` 후 `OPENROUTER_MODEL=<무료 모델 이름>`. 같은 회사 모델 둘(`subagent`)은 서로 다른 회사 둘보다 의견이 덜 갈린다 — 보고에 그 사실을 적는다.
codex·gemini 없이 OpenRouter나 서브에이전트만 쓸 때는 1단계의 `resolve_top_models.py`가 필요 없다. Claude 쪽은 세션 기본 모델을 쓰고(`claudeAlias` 생략), 둘째는 위 표대로 정한다.

출처: 직접 만든 것. 하네스 설계안을 두 회사의 최상위 모델에 반증시켜 걸러내던 방식을 스킬로 고정했다. 외부 차용 없음.

## 언제 쓰나 / 안 쓰나

- **쓴다**: 설계·규칙·절차·구조 판단 — 사용자가 답할 필요가 없는 기술 결정. 제안을 사용자에게 올리기 **전에** 한 번.
- **안 쓴다**: 사업 판단·고객 관계·돈 쓰는 결정·되돌릴 수 없는 실행 승인 → 그건 사용자 몫이다(이 스킬 결과를 근거로 붙여 올린다).
- 사실 확인(파일이 있나, 값이 몇인가)은 모델에게 묻지 말고 **직접 잰다.** 모델 의견은 판단용이다.

## 급 라우팅 — top이냐 mid냐

판단 질문에 어느 급을 붙일지는 부르는 세션이 정한다.
- **top(이 스킬)** = 다파일·아키텍처·보안·권한·돈·데이터 손실·되돌릴 수 없는 결정·릴리스 게이트·사용자에게 올릴 설계안.
- **mid** = 한 기능 안의 설계 선택, 문서·규칙 구조, 1차 리뷰 반증, 네이밍·API 모양처럼 틀려도 되돌리기 쉬운 것. 같은 절차에 `--tier mid`만 바꾼다.
- 오타·단문·단일 조회는 묻지 않는다. 한 급 안에서 애매하면 **보안·돈·권한 키워드 하나라도 걸리면 top**, 아니면 mid.
- 같은 질문을 mid에 먼저 돌리고 top으로 올리는 2단은 하지 않는다 — 왕복이 질문보다 비싸진다.

## 절차

### 1. 모델 찾기 (하드코딩 금지 — codex를 쓸 때)

```bash
python3 <이 스킬 폴더>/resolve_top_models.py            # --tier top (기본)
python3 <이 스킬 폴더>/resolve_top_models.py --tier mid
```
- **정본은 모델 대응표 파일**이다. 기본 위치 `~/.claude/model-tiers.md`, 다른 곳에 두면 환경변수 `MODEL_TIERS_FILE`로 가리킨다. 모델이 바뀌면 이 표만 고친다. 표 모양(첫 칸이 급 이름, 둘째 칸이 현재 모델):

```markdown
| 급 | 현재 대응 |
|---|---|
| Claude 최상위 | <지금 Claude 최상위 모델 이름> |
| Claude 상위 | <그 아래 급 모델 이름> |
| OpenAI 최상위 코딩급 | <최상위 모델의 슬러그, 예: gpt-… > |
| OpenAI 주력 | <주력 모델의 슬러그> |
```
  top = "Claude … 최상위" 행 + "OpenAI … 최상위" 행, mid = "Claude 상위" 행 + "OpenAI … 주력" 행.
- OpenAI 쪽: 표의 슬러그를 `~/.codex/models_cache.json`(보이는 모델·API 지원·은퇴 예정 아님)으로 검증한다. 표에 있는데 캐시에 없으면 exit 2. `matched_marker`에는 description에서 처음 일치한 최상위 표지어가 담긴다(표로 지정한 모델에 일치가 없으면 null).
- Claude 쪽: 표의 첫 단어를 소문자로 → Agent 도구 별칭.
- 표 파일이 없는 머신은 top만 캐시에서 고르고 결과에 `source=cache-fallback`이 찍힌다. OpenAI는 위 필터를 통과한 모델 중 description을 소문자로 비교해 `frontier`, `most capable`, `most demanding` 중 하나가 있는 모델만 고른다(목록 정본: 스크립트 상단 `OPENAI_TOP_MARKERS`). 여러 개면 그중 `priority`가 가장 작은 모델을 고른다. 하나도 없으면 `ok=false`, 이유 `최상위 표지어 일치 모델 없음, 후보 N개`, exit 2로 실패하며 priority로 되돌아가지 않는다. Claude는 description의 `Most capable`로 고른다. (`priority`는 표시 순서지 서열이 아니다 — GOTCHAS 참조)
- **추론 강도 변수 `ASK_TOP_EFFORT`** (기본 `medium`). 모델이 지원하지 않는 값이면 지원 목록의 가운데 값. Claude 쪽은 같은 변수를 Claude가 받는 값 목록(low~max)으로 따로 판정한다 — 두 회사 값 목록이 다르다.
- exit 2(한쪽 못 찾음)면 **멈추고 보고**한다. 다른 모델로 몰래 대체하지 않는다 — "못 찾음"을 "그 모델로 돌렸다"와 합치지 않는다.
- 결과의 급·모델명·강도·source를 최종 보고 첫 줄에 적는다.
- 쓰는 법 예시: 표에 최상위 모델을 적어 두고 `ASK_TOP_EFFORT=high python3 resolve_top_models.py`를 돌리면 `{"claude": {"agent_alias": "...", "effort": "high"}, "openai": {"model": "...", "effort": "high"}}` 한 줄이 나온다. 모델 이름은 코드가 아니라 이 출력에서 읽는다.

### 2. 브리프 파일 쓰기

`<작업폴더>/brief.md` 하나에 아래 순서로. **우리 결론을 먼저 보여 주지 않는다**(앵커링 방지 — 순위 라벨에 끌려가는 사례가 있었다).
1. **질문** — 사용자 원문 그대로(요약 금지) + 무엇을 정해야 하는지
2. **실측 사실** — 숫자·경로·근거. 추정은 추정이라 표시
3. **제약** — 이미 확정된 결정, 금지선(되돌리면 안 되는 것)
4. **우리 현재 안** — 맨 뒤에. "결함부터 찾아라, 동의는 결함을 못 찾은 뒤에만"을 붙인다
비밀값·고객 개인정보는 넣지 않는다.

### 3. 두 모델에게 같은 브리프로 동시에 묻기

요구 순서(두 모델 동일):
- **A. 네 답** — 우리 안을 보기 전에 질문에 대한 너의 답과 판정 기준.
- **B. 우리 안 반박** — 결함부터. 분리 자체가 틀린 접근일 가능성도 열어 둔다.
- **C. 발견마다 4칸** — 등급(암=지금 막아야 함 / 용종=이번에 고침 / 담배=기록만) · 안 하면 무엇이 언제 깨지나 · 하면 얻는 것 · 권고.
- **D. 모르는 것** — 브리프만으로 판단 못 하는 것.
- **E. 직접 확인한 것** — 브리프 숫자·주장 중 스스로 계산·대조한 것 1개 이상, 없으면 "없음". (첫 실행에서 값을 낸 건 의견이 아니라 한 모델의 합계 재계산이었다 — 의견만 받으면 그럴듯한 반박이 하나 늘 뿐)

실행(병렬) — `<이 스킬 폴더>/ask.workflow.js` 파일 내용을 먼저 읽고, 읽은 전문을 Workflow의 `script` 인자로 그대로 넘긴다. `args`는 아래와 같다:
```
Workflow({ script: "<읽은 ask.workflow.js 내용 전체>",
           args: { dir: "<작업폴더 절대경로>", claudeAlias: "<claude.agent_alias, 생략 가능>", claudeEffort: "<claude.effort, 생략 가능>",
                   secondBackend: "codex|openrouter|gemini|subagent", secondModel: "<openai.model 또는 OpenRouter 모델 이름>", secondEffort: "<openai.effort, codex만>",
                   skillDir: "<이 스킬 폴더 절대경로, openrouter에 필요>" } })
```
`scriptPath`로 직접 호출하면 `scriptPath must be a script path this tool returned, or a file you can already read`로 거부된다.
스크립트가 하는 일:
- **Claude**: Workflow 한 번에 `agent(prompt, {model: <agent_alias>, effort: <effort>})` — 브리프 경로를 주고 결과를 `<작업폴더>/claude-out.md`에 쓰게 한다.
- **둘째 목소리**: 같은 Workflow 안의 중계 agent(작은 모델, 옮기기만)가 `secondBackend`에 맞는 명령을 Bash로 돌린다. codex면
  `codex exec -m <model> -c model_reasoning_effort="<effort>" -s read-only --skip-git-repo-check - < prompt.md > openai-out.md`
  (timeout 580초, 실패 시 한 단계 낮은 강도로 1회 재시도 — 재시도했으면 보고에 적는다). openrouter면 `python3 ask_openrouter.py second-prompt.md --model <이름> --attach <작업폴더>/brief.md`, gemini면 `gemini -m <이름> -p "$(cat second-prompt.md)"`. 중계자는 해석·가감 금지. 결과는 `<작업폴더>/second-out.md`.

OpenRouter 모델은 내 컴퓨터 파일을 못 읽는다 — 브리프·기획 문서처럼 읽어야 할 파일은 `--attach`로 내용을 같이 보낸다(여러 개면 여러 번).

**Workflow 도구가 없을 때**: 같은 일을 손으로 나눠 한다. ① 위 A~E 요구와 브리프 경로를 담은 글을 `<작업폴더>/second-prompt.md`로 저장 ② Bash로 둘째 목소리 명령(위 codex·openrouter·gemini 줄 중 하나)을 백그라운드로 돌려 `<작업폴더>/second-out.md`에 받기 ③ 그동안 Agent 도구로 Claude 서브에이전트 하나에 같은 글을 주고 `<작업폴더>/claude-out.md`에 쓰게 하기. 두 쪽이 서로의 답을 보기 전에 끝나야 한다 — 한쪽 답을 다른 쪽에 넘기지 않는다.

**아직 직접 돌려 보지 못한 길**: OpenRouter 호출(`ask_openrouter.py`)은 키 없음·모델 없음 처리와 JSON 뽑기만 시험했고 실제 호출은 하지 않았다. gemini CLI 호출 모양도 설치본으로 확인하지 못했다. 돌려 보고 안 되면 이슈로 알려 달라.

### 4. 종합 (메인 세션)

- **합의** / **갈림** / **한쪽만 본 것**으로 나눈다. 갈린 곳은 "누가 맞나"를 **근거(실측 가능 여부)**로 가르고, 가를 수 없으면 그대로 둔다.
- 결론은 메인이 낸다. 사용자에게 올리는 건 **사업 도메인 또는 되돌릴 수 없는 것**만 — 나머지는 결론과 근거만 보고하고 진행한다.
- 발견 보고는 `## 발견` 블록 4칸 형식(등급·안 하면·하면·권고). 담배는 사용자에게 올리지 않고 결과 파일에만.
- 두 모델의 원문을 `<작업폴더>/`에 보존하고 경로를 적는다(원문 없으면 인용 재검 불가).

## 출력 형식

```
사용 모델(<급>): Claude=<alias 또는 세션 기본> / 둘째=<백엔드>:<model> · 강도=<effort> (요청 <requested>) · 출처=<source>
결론: <한 문단>
합의: …
갈림: … (근거로 가른 결과 / 못 가름)
## 발견
- [암|용종|담배] <무엇> — 안 하면: … / 하면: … / 권고: …
사용자에게 올릴 것: <사업·비가역만, 없으면 "없음">
원문: <경로들>
```

## 채점 모드 — 기획이 끝나면 근거로 점수를 매기고, 미달이면 보강

기획이 끝나면 근거에 기반해 점수를 매기고, 점수가 안 나오면 기획을 보강하게 하는 모드다. 급은 **mid 고정**이고, 모델은 늘 `resolve_top_models.py --tier mid`로 고른다. 이 글과 코드에는 모델 이름을 적지 않는다.

- **채점표·합격선 정본**: `score/rubric.md` 한 파일(두 모델에 같은 글). 고칠 때는 이 파일만.
- **누가 채점하나**: 기획을 쓴 세션이 아니다 — 두 모델이 각자 문서를 직접 열어 채점하고, 기획 세션은 합치기 스크립트만 돌린다.

절차(작업 폴더 `<기획 폴더>/score-r<회차>/`):
1. `python3 <이 스킬 폴더>/resolve_top_models.py --tier mid` — exit 2면 멈추고 보고(다른 급으로 대체 금지). 강도는 `ASK_TOP_EFFORT`(기본 medium).
2. 지시문: `python3 <이 스킬 폴더>/score/build_prompt.py <기획 문서 절대경로> > <작업 폴더>/prompt.md`
3. 동시에 둘:
   - Claude: `Agent({model: <claude.agent_alias>, effort: <claude.effort>, prompt: "<prompt.md 전문>\n\n답 JSON을 <작업 폴더>/claude-score.json 에만 쓰고(그 밖 파일 수정 금지) 같은 JSON을 반환하라."})`
   - 둘째(codex): `bash <이 스킬 폴더>/score/score_openai.sh <기획 문서> <작업 폴더> <openai.model> <openai.effort>` (백그라운드 가능, 결과 `openai-score.json`)
   - 둘째(OpenRouter): `python3 <이 스킬 폴더>/ask_openrouter.py <작업 폴더>/prompt.md --model <모델 이름> --attach <기획 문서 절대경로> --json > <작업 폴더>/openai-score.json` (결과 파일 이름은 같게 둔다)
4. 합치기: `python3 <이 스킬 폴더>/score/merge_scores.py --a <작업 폴더>/claude-score.json --b <작업 폴더>/openai-score.json --a-name <claude.display> --b-name <둘째 모델 이름> --round <회차> --out <작업 폴더>/report.md`
   항목마다 낮은 점수, 0 대 2로 갈린 항목은 표시 — 기획 세션이 그 두 근거를 직접 대조한다. 종료 코드 0 합격 / 1 미달 / 2 입력 오류(채점 다시).
5. **영수증**: report.md 첫 줄을 기획 문서 맨 위 상태 줄 바로 아래에 붙인다(회차마다 교체, 원문 report.md 경로 함께).
6. **미달이면 보강**: 빈 곳 목록 순서대로 기획을 고치고, 회차를 하나 올린 새 작업 폴더(`score-r<회차+1>/`)에서 2~5를 다시 — 두 채점자가 고친 문서를 새로 읽어야 하고, 합치기만 다시 돌리면 옛 점수가 그대로 나온다. 재채점은 최대 3회(`rubric.md`의 `max_rescore`). 고칠 때 앞 글에 덧붙이지 말고 그 항목을 다시 쓴다. 빈 곳이 **사람만 아는 사실**(E 항목 — 실제 업무·고객·돈)이면 추측해 채우지 말고 사용자에게 묻고 '답 대기'로 둔다.
7. 재채점 3회 뒤에도 미달이면 [막힘]으로 보고한다 — 영수증·report.md 경로·남은 빈 곳. 사업 사실이 막힘이면 사용자에게 묻는다.

하지 않는 것: 합격선을 그 자리에서 낮추기 · 한 모델만으로 채점(채점은 서로 다른 모델 둘이어야 한다 — 서브에이전트 둘로는 하지 않는다) · 채점자에게 기획 요약을 대신 주기(문서 경로만).

테스트: `cd <이 스킬 폴더>/score && python3 -B -m unittest test_merge_scores`
