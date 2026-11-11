#!/usr/bin/env node
// Stop 훅: "실행 대신 제안"으로 턴을 끝내는 것을 막는다.
// 한국어·영어 지원: 영어 패턴은 대소문자를 구분하지 않는다.
//
// 왜: 계획과 검증이 끝난 일을 실행하지 않고 "착수 가능합니다", "원하시면 진행할게요" 같은
// 제안 문장으로 턴을 끝내면, 사람이 "해"라고 한 번 더 말해야 일이 굴러간다. 기억·문서로만 두면
// 재발하므로 기계로 막는다.
//
// 판정: 마지막 assistant 글의 끝부분(마지막 600자)에 아래 "제안·대기" 표현이 있으면 exit 2로 차단한다.
// 예외(막지 않음): ① `### 결정 필요` 양식(사람이 골라야 하는 진짜 분기) ② `[blocked]`/`차단됨` 보고
// ③ stop_hook_active(훅 재진입) ④ 글이 비었거나 transcript를 못 읽음(판정 불가 → 통과, 조용히 막지 않는다)
// ⑤ 환경변수 ALLOW_OFFER_ENDING=1(사람이 켜는 해제 스위치).
"use strict";
const fs = require("fs");

const OFFER_PATTERNS = [
  /착수\s*가능/, /착수할\s*수\s*있/, /착수해도\s*될/, /시작할\s*수\s*있(습니다|어요)/,
  /진행할까요/, /할까요\s*[?？]/, /하시겠(어요|습니까)\s*[?？]/,
  /원하시면/, /필요하시면/, /말씀(해|하)\s*주?시면/, /신호\s*주시면/, /지시(해|하)\s*주?시면/, /승인\s*주시면/,
  /언제든\s*(말씀|요청)/,
  /\bshall\s+I\s+(?:proceed|start|begin|continue)\b/i,
  /\bwould\s+you\s+like\s+me\s+to\b/i,
  /\blet\s+me\s+know\s+if\s+you\s+(?:want|need|would\s+like)\b/i,
  /\bI\s+can\s+(?:start|begin|proceed)\b/i,
  /\bwant\s+me\s+to\b/i,
];
// 판정 범위: 마지막 글의 끝에서 이 글자 수만 본다(보고 본문 중간의 인용·설명은 제외하려는 알고리즘 상수).
const TAIL_CHARS = 600;
const EXEMPT_PATTERNS = [/###\s*결정\s*필요/, /###\s*Decision\s+needed\b/i, /\[blocked\]/i, /차단됨/, /사람\s*승인\s*대기/];

function readStdin() { try { return fs.readFileSync(0, "utf8"); } catch { return ""; } }

function lastAssistantText(input) {
  if (typeof input.last_assistant_message === "string" && input.last_assistant_message.trim()) return input.last_assistant_message;
  const path = input.transcript_path;
  if (!path || !fs.existsSync(path)) return "";
  let rows = [];
  try { rows = fs.readFileSync(path, "utf8").split("\n").filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean); } catch { return ""; }
  for (let i = rows.length - 1; i >= 0; i--) {
    const r = rows[i];
    if (r.type !== "assistant" || r.isSidechain) continue;
    const c = r.message && r.message.content;
    if (!Array.isArray(c)) continue;
    const texts = c.filter((b) => b.type === "text").map((b) => String(b.text || ""));
    if (texts.length) return texts.join("\n");
  }
  return "";
}

function main() {
  if (process.env.ALLOW_OFFER_ENDING === "1") return;
  let input = {};
  try { input = JSON.parse(readStdin() || "{}"); } catch { return; }
  if (input.stop_hook_active) return;
  const text = lastAssistantText(input);
  if (!text.trim()) return;
  if (EXEMPT_PATTERNS.some((p) => p.test(text))) return;
  const tail = text.slice(-TAIL_CHARS);
  const hit = OFFER_PATTERNS.find((p) => p.test(tail));
  if (!hit) return;
  const m = tail.match(hit);
  process.stderr.write(
    `[실행 대신 제안 금지] 마지막 글 끝에 "${m ? m[0] : hit}" 가 있다. 계획·검증이 끝난 일은 묻지 말고 지금 실행하라. ` +
    `되돌릴 수 있는 일은 추천안으로 바로 간다. 정말 사람 결정(되돌릴 수 없는 일·진짜 분기)이면 ` +
    `"### 결정 필요 — <제목>" 양식으로 질문을 올리고, 아니면 제안 문장을 지우고 그 일을 실행한 뒤 결과를 보고하라.\n`,
  );
  process.exit(2);
}

main();
