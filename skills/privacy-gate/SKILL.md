---
name: privacy-gate
description: Checks files locally for secrets, personal data, and confidential business information before sending them to an outside AI, then chooses ALLOW, REDACT, SUMMARIZE, or BLOCK.
allowed-tools: Bash, Read, Glob, Grep
argument-hint: "[optional: target path] [optional: --scope diff|project] [optional: --out <report.md>]"
---

# /privacy-gate — 보내기 전 민감정보 검사

프로젝트 파일을 외부 AI(호스팅 모델 전부)에 보내기 전에, 내 컴퓨터 안에서 키·전화번호·이메일을 먼저 찾는다. 검사는 같은 폴더의 `scan.py`가 하며 Python 3 표준 라이브러리만 쓴다. `PRIVACY_SCAN_CMD`가 있으면 외부 검사기도 함께 돌린다.

## 준비와 인자

- 경로가 있으면 그 파일·폴더를 검사한다. 폴더는 안쪽까지 읽는다.
- 경로 없이 `--scope diff`(기본)이면 `--diff`로 검사한다. `git diff --name-only HEAD`의 변경 파일과 Git이 아직 추적하지 않는 파일 중 존재하는 파일이 대상이다. 삭제한 파일은 제외한다.
- `--scope project`면 현재 프로젝트 `.`을 검사한다.
- `--out <path>`: 보고서 위치. 기본은 현재 프로젝트의 `.privacy-gate/report.md`다. 위치 정보가 들어가므로 `.privacy-gate/`는 `.gitignore`에 넣는다.
- `PRIVACY_SCAN_CMD`는 선택 사항이다. 설정돼 있다면 명령이 받는 대상·보고서 인자를 먼저 확인한다. 내장 검사기와 같은 범위를 검사해야 한다. Git 기록만 검사하는 도구로 현재 파일 검사를 대신하지 않는다.

## 실행 절차

### 1단계: 내장 검사기 실행

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/privacy-gate/scan.py" --diff
python3 "${CLAUDE_PLUGIN_ROOT}/skills/privacy-gate/scan.py" .
```

위 명령은 각각 변경 파일·프로젝트 전체를 검사하는 예다. `CLAUDE_PLUGIN_ROOT`가 없으면 스킬 폴더에서 프로젝트까지의 상대 경로를 확인해, **현재 프로젝트 폴더에서** `python3 <스킬 폴더의 상대 경로>/scan.py --diff` 또는 `python3 <스킬 폴더의 상대 경로>/scan.py .`을 실행한다. 경로는 따옴표로 감싼다. 특정 파일·폴더는 `--diff` 대신 경로들을 넘긴다.

출력은 JSON 한 덩어리이며 `files_scanned`, `skipped`, `findings`, `verdict`를 담는다. 발견 항목에는 `file`, `line`, `kind`만 있고 값·가린 미리보기는 없다. 파일 이름에 따른 발견은 `line=1`이다.

종료 코드: `ALLOW=0`, `REDACT=1`, `BLOCK=2`, 실행 오류 `3`. 1·2는 발견 결과이며 실행 실패와 구분한다. 오류면 JSON의 `BLOCK`과 함께 오류 안내를 내며, 검사 수는 완료된 수로 쓰지 않는다. 인자 오류·Git 오류·읽기 실패는 통과가 아니다.

`.git`, `node_modules`, 널 바이트가 있는 파일, 1MB(1,048,576바이트) 초과 파일, 심볼릭 링크와 일반 파일이 아닌 항목은 건너뛴다. 제외 폴더·링크는 항목당 한 번 세며 안쪽 파일 수까지 세지는 않는다. 건너뛴 항목이 있으면 미검사 범위를 보고하고, 그 내용까지 안전하다고 말하지 않는다. 파일 이름 검사는 크기·바이너리 검사보다 먼저 하므로 큰 `.env`도 차단한다.

### 2단계: 외부 검사기와 합치기

`PRIVACY_SCAN_CMD`가 없으면 내장 결과만 쓴다. 있으면 **반드시 그것도 실행**하고 두 결과를 합쳐 `BLOCK > REDACT > ALLOW` 순서로 더 엄한 것을 쓴다. 외부 검사기의 시크릿 발견은 `BLOCK`이다. 외부 도구의 종료 코드와 출력 형식은 해당 도구 기준으로 확인한다.

설정한 외부 검사기를 찾을 수 없거나 실행 실패·출력 해석 실패가 나면 멈추고 알린다. 내장 결과가 깨끗해도 대신 통과시키지 않는다. 외부 도구의 원시 출력에는 값이 있을 수 있으므로 터미널·대화에 직접 내보내지 않는다. 도구의 값 숨김 옵션이나 로컬 처리로 파일·줄·종류만 남긴다. 원본 보고서도 외부 AI에 보내거나 저장소에 넣지 않는다.

### 3단계: 문서 성격을 보고 최종 선택

| 판정 | 조건 | 외부 AI에 보내기 |
|------|------|----------------|
| `ALLOW` | 검사 완료, 발견 없음, 별도 민감 문서도 아님 | 검사한 범위만 가능 |
| `REDACT` | 전화번호·이메일·주민등록번호 모양 또는 위험 파일 이름만 발견 | 가린 사본을 다시 검사한 뒤 가능 |
| `SUMMARIZE` | 사람이/모델이 문서 성격을 보고 민감한 업무 문서·데이터로 판단 | 로컬에서 만든 요약을 다시 검사한 뒤 요약만 가능 |
| `BLOCK` | 키·개인키·키 대입 또는 `.env` 발견 | 원본 전송 불가 |

내장 검사기는 `SUMMARIZE`를 내지 않는다. 이 선택은 스캐너 통과 뒤에도 필요한 문서 검토 단계다. `BLOCK`을 요약 선택으로 낮추지 않는다. 문서 성격을 보겠다는 이유로 검사 전 원본을 외부 AI에 보내지 않는다.

검사 종류:
- `private_key`, `aws_key`, `github_token`, `slack_token`, `sk_key`, `assignment`, `env_file` → `BLOCK`
- `phone`, `email`, `resident_id`, `risky_name`만 → `REDACT`
- `.env`와 `.env.*`는 내용이 비어 있어도 `env_file`이다.
- 이름에 `credential`, `secret`, `dump`, `backup`이 있으면 `risky_name`이다.
- `api_key/secret/token/password = "..."`처럼 따옴표로 감싼 값이 8자 이상인 대입도 찾는다.

### 4단계: 결과 보고

최종 판정, 검사 범위, 검사한 파일 수, 건너뛴 수, 종류별 발견 수, 위치(파일·줄)와 다음 행동만 보고한다. 수는 실제 결과에서 계산한다. 비밀값 자체나 가린 미리보기를 화면·답변·보고서에 옮기지 않는다.

`BLOCK`이면 원본 전송을 멈추고, 키를 안전한 별도 보관소나 환경변수로 옮기고 `.env`가 `.gitignore`에 있는지 확인하도록 안내한다. 노출된 키는 폐기·재발급을 안내한다. 수정이나 가림은 자동으로 하지 않고, 처리한 뒤 다시 검사한다.

## 알려진 한계

- 정규식 검사라 새 키 형식·띄어 쓴 전화번호·사진 속 글자는 못 잡으며 해외 전화번호는 검사하지 않는다.
- 예시·테스트에 쓰는 가짜 값(010-0000-0000, example.com 이메일)도 그대로 잡는다. 오탐을 줄이려고 제외하지 않는다.
- 문서의 업무상 기밀 여부나 값의 실제 유효성은 알 수 없다. 발견 없음은 안전 보장이 아니다.
- 건너뛴 파일·폴더는 내용 검사를 하지 않았다. 필요한 파일은 별도로 검사하고 전송 여부를 정한다.

## 하지 말 것

- 원본 파일 수정
- 자동 커밋·푸시
- 홈 폴더나 여러 프로젝트를 한꺼번에 무차별로 검사
- 로컬 AI 모델 하나만 믿고 안전 판정 (규칙 기반 스캐너 결과가 기준)
- 외부 LLM에 원본 파일 그대로 전달
