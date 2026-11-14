export const meta = {
  name: 'ask-top-models',
  description: '서로 다른 두 목소리(Claude 서브에이전트 + codex·gemini·OpenRouter 모델 또는 두 번째 서브에이전트)에게 같은 브리프로 독립 의견·반박을 동시에 받는다',
  phases: [{ title: 'Ask', detail: 'Claude 서브에이전트 + 둘째 목소리 병렬' }],
}
// args: dir(작업폴더, 필수) · claudeAlias/claudeEffort(없으면 세션 기본 모델) ·
//   secondBackend: 'codex'(기본) | 'openrouter' | 'gemini' | 'subagent' · secondModel · secondEffort(codex만) · skillDir(openrouter에 필요)
// 급(top/mid)은 호출자가 resolve_top_models.py --tier 로 정해 모델명만 넘긴다. openrouter 키는 환경변수 OPENROUTER_API_KEY(여기엔 쓰지 않는다)
const { dir, claudeAlias, claudeEffort, secondBackend = 'codex', secondModel, secondEffort, skillDir } = args
// 경로는 셸 인자로 감싼다(공백·특수문자 대비)
const shq = v => "'" + String(v).replace(/'/g, "'\\''") + "'"
const ASK = `아래 브리프 파일을 끝까지 읽고 답하라: ${dir}/brief.md
요구 순서:
A. 네 답 — 브리프 4절(우리 안)을 보기 전에 1절 질문에 대한 너의 답과 판정 기준.
B. 우리 안 반박 — 결함부터. 분리/접근 자체가 틀렸을 가능성도 열어 둔다. 동의는 결함을 못 찾은 뒤에만.
C. 발견마다 4칸 — 등급(암=지금 막아야 함 / 용종=이번에 고침 / 담배=기록만) · 안 하면 무엇이 언제 깨지나 · 하면 얻는 것 · 권고.
D. 모르는 것 — 브리프만으로 판단 못 하는 것.
E. 직접 확인한 것 — 브리프의 숫자·주장 중 네가 계산·대조로 직접 확인한 것 1개 이상(맞았는지 틀렸는지). 없으면 '없음'이라고 쓸 것. 의견만으로는 반박이 되지 않는다.
쉬운 한국어. 과장 금지. 브리프에 없는 사실을 지어내지 말 것.`
phase('Ask')
const out2 = `${dir}/second-out.md`
const relay = (cmd) => `너는 명령 중계자다. 해석·가감 금지.
1) 아래 [프롬프트]를 그대로 ${dir}/second-prompt.md 로 저장.
2) Bash(timeout 600000): ${cmd}
3) 실패·타임아웃이면 원인을 반환 첫 줄에 적고, codex면 강도를 한 단계 낮춰 1회만 재시도한다. 재시도했으면 그 사실도 적는다.
4) 모델의 최종 답변만 ${out2} 로 저장하고 그 전문을 반환.
[프롬프트]
${ASK}
(브리프 파일은 읽기 전용으로 cat으로 읽을 수 있다.)`
const second = () => {
  const m = shq(secondModel || '')
  if (secondBackend === 'codex') {
    const eff = shq("model_reasoning_effort=" + JSON.stringify(secondEffort || 'medium'))
    return agent(relay(`cd ${shq(dir)} && if command -v timeout >/dev/null 2>&1; then timeout 580 codex exec ${secondModel ? '-m ' + m : ''} -c ${eff} -s read-only --skip-git-repo-check - < second-prompt.md > second-raw.md 2>&1; else codex exec ${secondModel ? '-m ' + m : ''} -c ${eff} -s read-only --skip-git-repo-check - < second-prompt.md > second-raw.md 2>&1; fi`),
      { model: 'sonnet', effort: 'low', label: `codex:${secondModel || 'default'}`, phase: 'Ask' })
  }
  if (secondBackend === 'gemini') {
    return agent(relay(`cd ${shq(dir)} && gemini ${secondModel ? '-m ' + m : ''} -p "$(cat second-prompt.md)" > second-raw.md 2>&1`),
      { model: 'sonnet', effort: 'low', label: `gemini:${secondModel || 'default'}`, phase: 'Ask' })
  }
  if (secondBackend === 'openrouter') {
    // 키는 환경변수에서만 읽는다. 모델 이름은 secondModel 또는 환경변수 OPENROUTER_MODEL.
    return agent(relay(`cd ${shq(dir)} && python3 ${shq(skillDir + '/ask_openrouter.py')} second-prompt.md ${secondModel ? '--model ' + m : ''} > second-raw.md`),
      { model: 'sonnet', effort: 'low', label: `openrouter:${secondModel || 'env'}`, phase: 'Ask' })
  }
  // subagent: 같은 Claude Code 안의 두 번째 서브에이전트. 첫째와 다른 관점을 주려고 반대 입장에서 읽게 한다.
  return agent(`${ASK}\n\n너는 둘째 심사자다. 같은 질문을 첫째와 다른 쪽(우리 안이 틀렸다는 가정)에서 읽고 답하라.\n답 전문을 ${out2} 에 저장하고(이 파일 쓰기만 허용), 같은 전문을 반환하라.`,
    { ...(secondModel ? { model: secondModel } : {}), label: 'second-subagent', phase: 'Ask' })
}
const [c, o] = await parallel([
  () => agent(`${ASK}\n\n답 전문을 ${dir}/claude-out.md 에 저장하고(이 파일 쓰기만 허용, 그 외 파일 수정 금지), 같은 전문을 반환하라.`,
    { ...(claudeAlias ? { model: claudeAlias } : {}), ...(claudeEffort ? { effort: claudeEffort } : {}), label: `claude:${claudeAlias || 'session'}`, phase: 'Ask' }),
  second,
].map(f => () => f()))
return { claude: c, second: o }
