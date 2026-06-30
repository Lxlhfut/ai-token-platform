import json, urllib.request, urllib.error

KEY = "sk-74aab4b4e384b61260fd16f8972591a1f706910c9d59d225"
BASE = "http://120.26.162.115"
BODY = {"model": "deepseek-v4-pro", "max_tokens": 500, "messages": [{"role": "user", "content": "say hi"}]}
HDR = {"Content-Type": "application/json", "x-api-key": KEY}

# 1) OpenAI 端点
print("=== OpenAI /v1/chat/completions ===")
r1 = urllib.request.Request(f"{BASE}/v1/chat/completions", data=json.dumps(BODY).encode(), headers=HDR, method="POST")
try:
    d1 = json.loads(urllib.request.urlopen(r1).read())
    print("choices:", d1.get("choices", [{}])[0].get("message", {}).get("content", "(空)"))
except urllib.error.HTTPError as e:
    print("❌", e.code, e.read().decode()[:200])

# 2) Anthropic 端点
print("\n=== Anthropic /v1/messages ===")
r2 = urllib.request.Request(f"{BASE}/v1/messages", data=json.dumps(BODY).encode(), headers=HDR, method="POST")
try:
    d2 = json.loads(urllib.request.urlopen(r2).read())
    print("content:", d2.get("content"))
    print("raw_id:", d2.get("id"))
except urllib.error.HTTPError as e:
    print("❌", e.code, e.read().decode()[:200])
