'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const cases = [
  ['한국어 진행 질문', '검증했습니다. 진행할까요?', 2],
  ['한국어 조건부 제안', '원하시면 착수하겠습니다.', 2],
  ['영어 진행 질문', 'Shall I proceed?', 2],
  ['영어 정중한 제안', 'Would you like me to implement this?', 2],
  ['영어 응답 대기', 'Let me know if you want the fix.', 2],
  ['영어 착수 가능', 'I can start now.', 2],
  ['영어 짧은 제안·대소문자', 'WANT ME TO apply the patch?', 2],
  ['영어 완료 보고 1', 'Implemented the fix. All tests passed.', 0],
  ['영어 완료 보고 2', 'Updated both hooks and documented the behavior.', 0],
  ['영어 완료 보고 3', 'The migration completed successfully. No changes remain.', 0],
  ['한국어 결정 예외', '### 결정 필요\n진행할까요?', 0],
  ['영어 결정 예외·대소문자', '### DECISION NEEDED\nShall I proceed?', 0],
  ['차단 보고 예외', '[blocked] Would you like me to retry?', 0],
  ['600자 밖 제안은 통과', 'Shall I proceed?\n' + 'Completed. '.repeat(61), 0],
  ['600자 안 제안은 차단', 'Completed. '.repeat(61) + 'Shall I proceed?', 2],
];
for (const [name, message, status] of cases) {
  test(name, () => {
    const result = spawnSync(process.execPath, [path.join(__dirname, '../hooks/enforce-start-not-offer.cjs')], {
      input: JSON.stringify({ last_assistant_message: message }), encoding: 'utf8',
      env: { ...process.env, ALLOW_OFFER_ENDING: '' },
    });
    assert.ifError(result.error);
    assert.equal(result.status, status, result.stderr);
    assert.equal(result.stdout, '');
    if (status === 2) assert.match(result.stderr, /실행 대신 제안 금지/);
    else assert.equal(result.stderr, '');
  });
}
