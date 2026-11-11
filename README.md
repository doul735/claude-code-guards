English: [README.en.md](README.en.md)

# claude-code-guards

**"할까요?"로 끝나는 답, 한 번 물었더니 뒤집힌 계획, 몰래 번식하는 서브에이전트. Claude Code의 이런 버릇을 막아 주는 훅과 규칙 모음.**

Node.js만 있으면 돈다. 한 레포에 계속 추가한다. 지금은 첫 묶음이다.

## 설치

Claude Code 안에서 두 줄.

```
/plugin marketplace add doul735/claude-code-guards
/plugin install code-guards@jeondaeli
```

셸에서는 `claude plugin marketplace add doul735/claude-code-guards` 다음 `claude plugin install code-guards@jeondaeli`. 설치 뒤 새 세션에서 `/hooks`로 훅 등록을 본다. 나중에 늘어나는 것도 같은 플러그인으로 들어온다.

## 이런 적 있죠?

| 이름 | 이런 적 있죠? | 하는 일 | 종류 |
|---|---|---|---|
| enforce-start-not-offer | 다 끝났는데 "진행할까요?"로 턴이 끝남 | 제안만 하고 끝내는 답을 막고 바로 실행하게 돌려보냄 | 훅 |
| enforce-no-plan-flip | 질문 한 번에 확정한 계획을 AI가 바꿔 버림 | 바꾸라는 지시 없이 계획을 뒤집으면 막고 근거부터 설명하게 함 | 훅 |
| block-subagent-nesting | 서브에이전트가 또 서브에이전트를 불러 결과가 사라짐 | 서브에이전트 안의 Agent 호출을 막음 | 훅 |
| assumptions-and-corrections | 정정했는데 앞 답에 덧붙여 고치다 더 꼬임 | 확정한 것과 AI 가정을 나눠 적고, 정정하면 확정 목록만으로 다시 만들게 함 | 규칙 |

규칙의 연구 논문 출처는 파일 맨 위에 적어 두었다.

## 규칙 파일은 따로 복사

플러그인은 `CLAUDE.md`나 규칙 파일을 컨텍스트에 싣지 않는다. 규칙은 직접 둔다.

1. `rules/assumptions-and-corrections.md`를 `~/.claude/rules/`(또는 프로젝트의 `.claude/rules/`)에 복사
2. `CLAUDE.md`에서 그 파일을 읽게 한다

## 수동 복사로 설치

플러그인 없이 쓰려면 `hooks/*.cjs`를 `~/.claude/hooks/`로 복사하고 `~/.claude/settings.json`에 등록한다. 이미 `hooks` 칸이 있으면 배열에 합친다.

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "node ~/.claude/hooks/enforce-start-not-offer.cjs" },
          { "type": "command", "command": "node ~/.claude/hooks/enforce-no-plan-flip.cjs" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Agent|Monitor|Bash",
        "hooks": [
          { "type": "command", "command": "node ~/.claude/hooks/block-subagent-nesting.cjs" }
        ]
      }
    ]
  }
}
```

훅마다 끄는 법(환경변수)과 알려진 한계는 파일 맨 위 주석에 있다. 문장 판정은 한국어·영어 기준이다.

## 계속 늘어남 — 다음에 올 것

- 여러 모델에게 같은 질문을 던져 독립 반박을 받는 스킬
- 외부 AI에 보내기 전 키·개인정보를 로컬에서 거르는 스킬
- AI와 끝까지 반박을 주고받는 토론 스킬
- 개인정보 파일을 AI가 보지 않고 처리하는 절차
- 리뷰 지적을 한 번에 모아 감사하는 스킬
- 요구를 듣고 초안을 한 번에 내는 스킬 둘

쓰다가 막히거나 빠진 버릇이 있으면 이슈로 알려 달라.

## 라이선스

MIT. LICENSE 참조.
