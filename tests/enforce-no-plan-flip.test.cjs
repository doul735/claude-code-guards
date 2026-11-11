'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const cases = [
  ['한국어 계획 변경', '계획을 변경합니다.', 2, '원래 계획이 뭐였나요?'],
  ['한국어 순서 변경', '순서를 앞당기겠습니다.', 2, '원래 순서가 아니었나요?'],
  ['영어 계획 변경', 'Let me change the plan.', 2],
  ['영어 방향 변경', 'I will switch to the alternative approach.', 2],
  ['영어 대신 실행·대소문자', "INSTEAD, LET'S implement phase two first.", 2],
  ['영어 순서 변경', 'I will reorder the sequence.', 2],
  ['영어 일정 앞당김', 'I will move the testing phase forward.', 2],
  ['영어 완료 보고 1', 'Implemented the fix. All tests passed.', 0],
  ['영어 완료 보고 2', 'Completed phase one according to the approved plan.', 0],
  ['영어 완료 보고 3', 'Updated the documentation. The existing order remains unchanged.', 0],
  ['영어 일반 진행 표현', 'The team is moving forward as planned.', 0],
  ['한국어 제안 예외', '변경 제안으로 계획을 변경하는 방법이 있습니다.', 0],
  ['영어 제안 예외', 'I propose we change the plan after approval.', 0],
  ['영어 제안에도 실행 약속이면 차단', 'I propose a change and I will switch to phase two.', 2],
  ['영어 제안 부정이면 차단', 'This is not a proposal; let me change the plan.', 2],
  ['영어 명시적 변경 지시 예외', 'Let me change the plan.', 0, 'Why this order? Please change the plan.'],
  ['영어 질문은 변경 지시 아님', 'Let me change the plan.', 2, 'Why would we change the plan?'],
  ['한국어 명시적 변경 지시 예외', '계획을 변경합니다.', 0, '원래 순서가 뭐였나요? 계획을 변경해.'],
];
for (const [name, message, status, user = 'Why was this order chosen?'] of cases) {
  test(name, (t) => {
    // Fixtures stay inside this repository, including when TMPDIR points elsewhere.
    const dir = fs.mkdtempSync(path.join(__dirname, '.plan-flip-'));
    t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
    const transcript = path.join(dir, 'transcript.jsonl');
    fs.writeFileSync(transcript, [
      { type: 'user', message: { content: user } },
      { type: 'assistant', message: { content: [{ type: 'text', text: message }] } },
    ].map(JSON.stringify).join('\n'));
    const result = spawnSync(process.execPath, [path.join(__dirname, '../hooks/enforce-no-plan-flip.cjs')], {
      input: JSON.stringify({ transcript_path: transcript }), encoding: 'utf8',
      env: { ...process.env, ALLOW_PLAN_FLIP: '', PLAN_FLIP_LOG: '' },
    });
    assert.ifError(result.error);
    assert.equal(result.status, status, result.stderr);
    assert.equal(result.stdout, '');
    if (status === 2) assert.match(result.stderr, /확정 계획 뒤집기 금지/);
    else assert.equal(result.stderr, '');
  });
}
