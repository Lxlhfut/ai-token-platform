#!/usr/bin/env python3
"""
独立 OpenAI SDK 兼容性测试（模拟 Cursor/Claude Code/Copilot 等工具的集成路径）
无 urllib，纯 SDK，避免 Windows TLS 冲突
"""

import sys, traceback

API_KEY = "sk-be24c3885a94455e6a60f0b21ecf592df8c35d7b0accf397"
API_BASE = "http://localhost:8000"
TEST_MODEL = "qwen-turbo"

passed = 0
failed = 0

def ok(msg, detail=""):
    global passed
    passed += 1
    print(f"  [OK]    {msg}" + (f"  -> {detail}" if detail else ""))

def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  [FAIL]  {msg}" + (f"  -> {detail}" if detail else ""))

try:
    import openai
    print(f"\n  openai SDK v{openai.__version__} | base_url={API_BASE}/v1")
    print(f"  Test model: {TEST_MODEL}\n")

    client = openai.OpenAI(base_url=f"{API_BASE}/v1", api_key=API_KEY, timeout=30)

    # 1) Models list - 所有工具连接验证都需要
    print("=" * 50)
    print("  1) client.models.list()")
    models = client.models.list()
    names = [m.id for m in models.data]
    ok(f"models.list()", f"{len(names)} models: {', '.join(names[:6])}...")

    # 2) Non-streaming chat - 等同于 curl
    print("=" * 50)
    print(f"  2) client.chat.completions.create() non-stream [{TEST_MODEL}]")
    resp = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "Reply exactly: SDK_WORKS"}],
        temperature=0,
    )
    reply = resp.choices[0].message.content.strip()
    usage = resp.usage
    ok(f"chat.create() non-stream",
       f"reply='{reply}' | tokens(p={usage.prompt_tokens} c={usage.completion_tokens})")

    # 3) Streaming chat - Cursor 对话核心路径
    print("=" * 50)
    print(f"  3) client.chat.completions.create() stream [{TEST_MODEL}]")
    stream = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "Reply exactly: STREAM_OK"}],
        temperature=0,
        stream=True,
    )
    chunks = []
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
    full = "".join(chunks).strip()
    ok(f"chat.create() stream", f"reply='{full}' | {len(chunks)} chunks")

    # 4) 带 system prompt - Claude Code / Copilot 常用模式
    print("=" * 50)
    print(f"  4) chat with system prompt [{TEST_MODEL}]")
    resp = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[
            {"role": "system", "content": "You are a code assistant. Reply ONLY with the word OK."},
            {"role": "user", "content": "hello"},
        ],
        temperature=0,
    )
    ok("system prompt", f"reply='{resp.choices[0].message.content.strip()}'")

    # 5) 多轮对话 - 典型 IDE Copilot 场景
    print("=" * 50)
    print(f"  5) multi-turn conversation [{TEST_MODEL}]")
    resp = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[
            {"role": "user", "content": "What is 1+1? Reply just the number."},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "Now multiply by 2. Reply just the number."},
        ],
        temperature=0,
    )
    ok("multi-turn", f"reply='{resp.choices[0].message.content.strip()}'")

except Exception as e:
    fail("OpenAI SDK", str(e))
    traceback.print_exc()

print(f"\n{'='*50}")
print(f"  Result: {passed}/{passed+failed} passed [{'ALL GREEN!' if failed == 0 else 'SOME FAILED'}]")
print(f"{'='*50}")
