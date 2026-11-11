#!/usr/bin/env node
// Stop 훅: 사용자의 질문 한 번에 확정된 계획을 뒤집는 응답을 막는다.
// 한국어·영어 지원: 영어 패턴은 대소문자를 구분하지 않는다.
//
// 왜: 사용자가 "원래 10개 아니었나?"처럼 묻기만 했는데, 현 계획을 설명하지 않고
// "순서를 당기는 게 맞습니다"라며 계획을 바꿔 버리는 일이 생긴다. 질문은 설명 요청이지 변경 지시가 아니다.
//
// 판정: 마지막 진짜 사용자 글이 질문이고 명시적 변경 지시가 없는데, 그 뒤 assistant 본문 또는
// SendMessage input.message에 계획 변경 표현이 있으면 exit 2. 시스템 글·tool_result·sidechain은 제외한다.
// 예외: 변경 표현과 같은 문장의 실행 약속 없는 제안, stop_hook_active, 판정 불가(조용히 통과),
// 환경변수 ALLOW_PLAN_FLIP=1(사람이 켜는 해제 스위치).
// 방향: 판정이 애매하면 막는다 — 오탐은 같은 턴 한 번 다시 쓰기로 끝나지만(stop_hook_active),
// 미탐은 뒤집기가 그대로 나간다. 알려진 오탐: 정중한 의문형 요청('바꿔줄래?'), 부정 설명('변경한 적 없습니다').
// 선택 기록: 환경변수 PLAN_FLIP_LOG에 파일 경로를 주면 차단마다 JSON 한 줄을 덧붙인다(없으면 기록 안 함).
"use strict";
const fs = require("fs");
const path = require("path");

const SYSTEM_PREFIX = /^(<system-reminder|<task-notification|<cross-session-message|\[SYSTEM NOTIFICATION)/;
const CHANGE_INSTRUCTION = /바꿔|바꾸자|당겨|앞당겨|변경해|수정해|고쳐|그렇게\s*해|그렇게\s*가|진행해|다시\s*짜|^(?:please\s+)?(?:change|revise|rework|reorder|switch|move\s+up|bring\s+forward)\b|^(?:please\s+)?(?:go\s+ahead|proceed|do\s+that)\b|^let[’\x27]s\s+(?:change|revise|rework|reorder|switch)\b/i;
const CHANGE_PATTERNS = [
  /순서(를)?\s*(당기|당깁|당겼|앞당기|바꾸|바꿉|바꿨|조정|뒤집)/,
  /계획(을)?\s*(바꾸|바꿉|바꿨|변경|뒤집|다시\s*짜|수정하|수정합|수정했)/,
  /(당기|앞당기|바꾸|뒤집)는\s*(게|것이)\s*맞/,
  /다시\s*짜(겠|자|기로)/,
  /앞당기(겠|기로|자)/,
  /(순서|계획|방향)을?\s*바꾸(겠|기로)/,
  // 다른 에이전트에게 보내는 "순서를 앞당겨라"도 잡는다(당기다의 명령형 활용).
  /순서(를)?\s*(앞)?당겨/,
  /\b(?:change|changing|revise|revising|rework|reworking|reorder|reordering)\s+(?:(?:the|our|this|current|existing|confirmed)\s+)*(?:plan|order|sequence|direction)\b/i,
  /\b(?:move|moving|bring|bringing)\s+(?:(?:the|our)\s+)?(?:\w+\s+){0,2}(?:step|phase|task|deadline|schedule|timeline)\s+(?:up|forward)\b/i,
  /\bI\s+(?:will|shall)\s+switch\s+to\b|\bI[’']ll\s+switch\s+to\b/i,
  /\binstead\s*,?\s*let[’']s\b/i,
];
const PROPOSAL_PATTERN = /변경 제안|제안으로|제안하겠|제안드|\b(?:propose|proposal|suggest|suggestion)\b/i;
// '변경 제안이 아니라 …합니다'처럼 제안을 부정하는 연결이 있으면 그 문장은 제안이 아니다.
const NEGATED_PROPOSAL = /아니라|대신|말고|\b(?:not|instead|rather\s+than)\b|\b(?:isn[’']t|aren[’']t)\b/i;
// 같은 문장에 실행 약속이 있으면 제안 문구로 면제하지 않는다.
const COMMIT_PATTERN = /지시하겠|지시했|지시를\s*보냈|바꾸겠|당기겠|앞당기겠|변경하겠|수정하겠|조정하겠|뒤집겠|바꾸라고\s*(했|전달)|당기라고\s*(했|전달)|변경합니다|조정합니다|바꿉니다|당깁니다|수정합니다|뒤집습니다|변경했습니다|조정했습니다|바꿨습니다|당겼습니다|수정했습니다|뒤집었습니다|\bI\s+(?:will|shall)\b|\bI[’']ll\b|\blet\s+me\b|\blet[’']s\b|\b(?:have\s+|has\s+)?(?:changed|revised|reordered|switched|instructed)\b/i;
const QUESTION_WORD = /왜|뭐|무엇|어떻게|어째서|어떤|\b(?:why|what|how|which|when|where|who)\b/i;
const QUESTION_ENDING = /(?:나요|나|까|니|냐|지\s*않나|인가|일까|할지)[.!?？。]*$/;
// 기록에 남기는 사용자 질문 앞부분 길이.
const USER_QUESTION_HEAD_CHARS = 80;

function readStdin() { try { return fs.readFileSync(0, "utf8"); } catch { return ""; } }

function sentences(text) {
  // 물음표를 남겨 질문과 그 뒤 별도 변경 지시를 구별한다.
  return (text.match(/[^.!?？。\r\n]+[.!?？。]*/g) || []).map((s) => s.trim());
}

function isQuestion(sentence) {
  return /[?？]$/.test(sentence) || QUESTION_WORD.test(sentence) || QUESTION_ENDING.test(sentence);
}

function messageText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content.filter((b) => b && b.type === "text" && typeof b.text === "string")
    .map((b) => b.text).join("\n");
}

function currentTurn(input) {
  if (typeof input.transcript_path !== "string" || !input.transcript_path) return null;
  // Stop 직전 assistant 행의 transcript 기록을 기다린다.
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 300);
  let rows;
  try {
    rows = fs.readFileSync(input.transcript_path, "utf8").split("\n").filter(Boolean)
      .map((line) => { try { return JSON.parse(line); } catch { return null; } }).filter(Boolean);
  } catch { return null; }
  for (let i = rows.length - 1; i >= 0; i--) {
    const row = rows[i];
    if (row.type !== "user" || row.isSidechain) continue;
    const userText = messageText(row.message && row.message.content).trim();
    if (!userText || SYSTEM_PREFIX.test(userText)) continue;
    const parts = [];
    for (const reply of rows.slice(i + 1)) {
      if (reply.type !== "assistant" || reply.isSidechain) continue;
      const content = reply.message && reply.message.content;
      parts.push(messageText(content));
      if (!Array.isArray(content)) continue;
      for (const block of content) {
        if (block && block.type === "tool_use" && block.name === "SendMessage" &&
            block.input && typeof block.input.message === "string") parts.push(block.input.message);
      }
    }
    // 기록 대기 후에도 마지막 답변이 빠질 수 있어 Stop 페이로드를 함께 검사한다.
    if (typeof input.last_assistant_message === "string") parts.push(input.last_assistant_message);
    return { userText, assistantText: parts.join("\n") };
  }
  return null;
}

function logBlock(input, hit, userText) {
  const file = process.env.PLAN_FLIP_LOG;
  if (!file) return;
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.appendFileSync(file, JSON.stringify({
      ts: new Date().toISOString(), hit,
      userQuestionHead: Array.from(userText).slice(0, USER_QUESTION_HEAD_CHARS).join(""),
      session_id: input.session_id ?? null,
    }) + "\n");
  } catch { /* 기록 쓰기 실패는 차단 판정에 영향을 주지 않는다. */ }
}

function main() {
  if (process.env.ALLOW_PLAN_FLIP === "1") return;
  let input;
  try { input = JSON.parse(readStdin() || "{}"); } catch { return; }
  if (!input || typeof input !== "object" || input.stop_hook_active) return;
  const turn = currentTurn(input);
  if (!turn || !(/[?？]/.test(turn.userText) || QUESTION_ENDING.test(turn.userText))) return;
  if (sentences(turn.userText).some((s) => CHANGE_INSTRUCTION.test(s) && !isQuestion(s))) return;
  let hit;
  for (const sentence of sentences(turn.assistantText)) {
    if (PROPOSAL_PATTERN.test(sentence) && !NEGATED_PROPOSAL.test(sentence) && !COMMIT_PATTERN.test(sentence)) continue;
    const pattern = CHANGE_PATTERNS.find((p) => p.test(sentence));
    if (pattern) {
      hit = sentence.match(pattern)[0];
      break;
    }
  }
  if (!hit) return;
  logBlock(input, hit, turn.userText);
  process.stderr.write(
    `[확정 계획 뒤집기 금지] 사용자가 질문했을 뿐인데 이번 턴에 계획 변경 표현("${hit}")이 있다. ` +
    "질문은 설명 요청이다 — 확정된 계획과 그 근거(어느 단계에서 무엇이 되는지, 왜 그 순서인지)를 먼저 설명하라. " +
    "계획에 실제 결함이 보이면 바꾸지 말고 계획 주인에게 근거·비용·영향을 담은 '변경 제안'으로 보내고, " +
    "사용자에게는 '현 계획 + 바꾸면 얻는 것·잃는 것'만 보여 줘라. 사용자가 명시적으로 바꾸라고 할 때만 바꾼다. " +
    "이미 다른 에이전트에게 변경 지시를 보냈다면 철회 메시지를 보내라.\n",
  );
  process.exit(2);
}

main();
