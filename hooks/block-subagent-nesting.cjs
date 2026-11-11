#!/usr/bin/env node
// PreToolUse 훅: 서브에이전트가 Agent를 다시 부르는 것(손자 호출)과 백그라운드 대기를 막는다.
//
// 왜: 서브에이전트 안에서 또 띄운 에이전트나 백그라운드 작업은 결과가 부모에게 돌아오지 않거나
// 다음 턴까지 묶여 유실될 수 있다. 더 쪼갤 일은 결과로 돌려주고 루트 세션이 띄운다.
//
// 판정: 훅 입력에 agent_id가 있으면(= 서브에이전트 안의 호출) Agent·Monitor·Bash(run_in_background=true)를
// exit 2로 막는다. 루트 세션 호출은 통과. 입력을 못 읽는 등 판정 오류는 통과.
// 해제(사람이 켬): ALLOW_SUBAGENT_NESTING=1.
// 선택 기록: 환경변수 SUBAGENT_NESTING_LOG에 파일 경로를 주면 걸린 호출마다 JSON 한 줄을 덧붙인다(없으면 기록 안 함).
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const NOTICE = "[서브에이전트 중첩 금지] 서브에이전트·팀원·Workflow 에이전트는 Agent·Bash 백그라운드·Monitor를 쓰지 않는다. 더 쪼갤 일은 결과로 돌려주고 루트 세션이 띄운다. 긴 명령은 전경(timeout 최대 600000)으로 끝내거나 결과 파일 경로를 남기고 끝낸다.";

function logHit(input, decision) {
  const log = process.env.SUBAGENT_NESTING_LOG;
  if (!log) return;
  try {
    fs.mkdirSync(path.dirname(log), { recursive: true });
    fs.appendFileSync(log, JSON.stringify({ ts: new Date().toISOString(),
      tool: input.tool_name,
      agent_type: typeof input.agent_type === "string" ? input.agent_type : "",
      session_id: typeof input.session_id === "string" ? input.session_id : "",
      decision }) + "\n");
  } catch { /* 기록 실패는 판정을 바꾸지 않는다. */ }
}

function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  if (typeof input?.agent_id !== "string" || input.agent_id.length === 0) return;
  const tool = input.tool_name;
  if (tool !== "Agent" && tool !== "Monitor" &&
      !(tool === "Bash" && input.tool_input?.run_in_background === true)) return;
  const decision = process.env.ALLOW_SUBAGENT_NESTING === "1" ? "allow_override" : "block";
  if (decision === "block") process.exitCode = 2;
  logHit(input, decision);
  if (decision === "block") fs.writeSync(2, `${NOTICE} 도구: ${tool}\n`);
}

try { main(); } catch { /* 판정 오류는 통과. 차단 판정 뒤에는 exit 2를 유지한다. */ }
