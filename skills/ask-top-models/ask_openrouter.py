#!/usr/bin/env python3
"""OpenRouter(openrouter.ai)로 모델 하나에 프롬프트 파일을 보내고 답을 표준 출력에 쓴다.

사용: ask_openrouter.py <프롬프트 파일> [--model <모델 이름>] [--json]
- 키: 환경변수 OPENROUTER_API_KEY (파일·인자로 받지 않는다. 키 값은 어디에도 출력하지 않는다.)
- 모델: --model, 없으면 환경변수 OPENROUTER_MODEL. 둘 다 없으면 멈춘다(모델 이름을 코드에 박지 않는다).
  이름은 https://openrouter.ai/models 의 표기를 그대로 쓴다. 무료 모델은 이름 끝에 ':free'가 붙는다.
- --json: 답에서 첫 JSON 객체만 뽑아 출력한다(채점 모드용). 못 뽑으면 exit 1.
종료 코드: 0 성공 / 1 호출 실패 / 2 키나 모델이 없음.
표준 라이브러리만 쓴다.
"""
import argparse, json, os, sys, urllib.request, urllib.error

URL = "https://openrouter.ai/api/v1/chat/completions"

def build_content(prompt: str, attachments: list[tuple[str, str]]) -> str:
    if not attachments:
        return prompt
    parts = [prompt, "", "아래는 위에서 말한 파일의 내용이다. 너는 로컬 파일을 열 수 없으니 이 내용만으로 판단하라."]
    for path, content in attachments:
        parts.extend([f"[첨부 파일: {path}]", content, "[첨부 끝]"])
    return "\n".join(parts)

def first_json_object(text):
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': in_str = False
            elif ch == '"': in_str = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.dumps(json.loads(text[start:i + 1]), ensure_ascii=False)
                    except ValueError:
                        break
        start = text.find("{", start + 1)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt_file")
    ap.add_argument("--model")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--attach", action="append")
    a = ap.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    model = a.model or os.environ.get("OPENROUTER_MODEL")
    if not key:
        print("OPENROUTER_API_KEY 환경변수가 없습니다", file=sys.stderr); return 2
    if not model:
        print("모델 이름이 없습니다 (--model 또는 OPENROUTER_MODEL)", file=sys.stderr); return 2
    with open(a.prompt_file, encoding="utf-8") as f:
        prompt = f.read()
    attachments = []
    for path in a.attach or []:
        try:
            with open(path, encoding="utf-8") as f:
                attachments.append((path, f.read()))
        except (OSError, UnicodeError):
            print(f"첨부 파일을 못 읽었습니다: {path}", file=sys.stderr); return 2
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": build_content(prompt, attachments)}]}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
        text = data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"OpenRouter 오류 HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}", file=sys.stderr); return 1
    except Exception as e:
        print(f"호출 실패: {type(e).__name__}", file=sys.stderr); return 1
    if a.json:
        obj = first_json_object(text)
        if obj is None:
            print("답에서 JSON 객체를 못 찾았습니다", file=sys.stderr); return 1
        text = obj
    print(text)
    return 0

if __name__ == "__main__":
    sys.exit(main())
