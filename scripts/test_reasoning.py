"""验证：Claude 模型名映射 + 推理模型 max_tokens 兜底"""
import json, urllib.request, urllib.error
from typing import Optional

KEY = "sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85"
BASE = "http://localhost:8000"

def test_anthro(model: str, max_tokens: Optional[int] = None):
    body = {"model": model, "messages": [{"role": "user", "content": "say hi"}], "stream": False}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    r = urllib.request.Request(f"{BASE}/v1/messages", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": KEY}, method="POST")
    try:
        resp = urllib.request.urlopen(r)
        d = json.loads(resp.read())
        c = d.get("content", [{}])[0].get("text", "")
        return f"✅ content={repr(c)}"
    except urllib.error.HTTPError as e:
        return f"❌ HTTP {e.code}: {e.read().decode()[:200]}"

def test_openai(model: str, max_tokens: int):
    body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": "say hi"}]}
    r = urllib.request.Request(f"{BASE}/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": KEY}, method="POST")
    try:
        resp = urllib.request.urlopen(r)
        d = json.loads(resp.read())
        c = d.get("choices", [{}])[0].get("message", {}).get("content", "")
        return f"✅ content={repr(c)}"
    except urllib.error.HTTPError as e:
        return f"❌ HTTP {e.code}: {e.read().decode()[:200]}"

print("=== 1) Claude 模型名 → 平台模型 ===")
print("  claude-3-5-sonnet-20241022:", test_anthro("claude-3-5-sonnet-20241022"))

print("\n=== 2) 推理模型 max_tokens 兜底 (Anthropic 端点) ===")
print("  max_tokens=30 (应被提升):", test_anthro("deepseek-v4-pro", 30))
print("  max_tokens=4096 (保持不变):", test_anthro("deepseek-v4-pro", 4096))

print("\n=== 3) 推理模型 max_tokens 兜底 (OpenAI 端点) ===")
print("  max_tokens=30:", test_openai("deepseek-v4-pro", 30))
print("  max_tokens=4096:", test_openai("deepseek-v4-pro", 4096))

print("\n=== 4) 非推理模型不受影响 ===")
print("  deepseek-chat max_tokens=30:", test_openai("deepseek-chat", 30))
