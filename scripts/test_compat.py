#!/usr/bin/env python3
"""
ai-token-platform 多工具兼容性测试
测试: /v1/models /v1/chat/completions(non-stream+stream) /billing/* + OpenAI SDK
使用: python scripts/test_compat.py
"""

import os, sys, json, urllib.request, urllib.error

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
API_KEY  = os.environ.get("API_KEY", "")
TEST_MODEL = os.environ.get("TEST_MODEL", "qwen-turbo")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

passed = 0
failed = 0

def step(name):
    print(f"\n{'='*60}")
    print(f"  {name}")

def ok(msg, detail=""):
    global passed
    passed += 1
    line = f"  [OK]    {msg}"
    if detail:
        line += f"  -> {detail}"
    print(line)

def fail(msg, detail=""):
    global failed
    failed += 1
    line = f"  [FAIL]  {msg}"
    if detail:
        line += f"  -> {detail}"
    print(line)

def http(method, path, body=None, raw=False):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
        with urllib.request.urlopen(req, timeout=60) as resp:
            if raw:
                return resp
            raw_body = resp.read().decode("utf-8")
            return resp.status, json.loads(raw_body) if raw_body else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")[:500]
        try:
            errj = json.loads(err)
        except:
            errj = {"error": err}
        return e.code, errj
    except Exception as e:
        return 0, {"error": str(e)}


# ======== Test 1: Models ========
step("Test 1: GET /v1/models")
code, data = http("GET", "/v1/models")
if code == 200 and data.get("object") == "list":
    models = [m["id"] for m in data.get("data", [])]
    ok("HTTP 200 + models list", f"{len(models)} models: {', '.join(models[:8])}")
else:
    fail("/v1/models", json.dumps(data, ensure_ascii=False)[:200])

# ======== Test 2: Chat non-stream ========
step(f"Test 2: POST /v1/chat/completions (non-stream) [{TEST_MODEL}]")
code, data = http("POST", "/v1/chat/completions", {
    "model": TEST_MODEL,
    "messages": [{"role": "user", "content": "Say hi in 3 words"}],
    "stream": False,
})
if code == 200 and "choices" in data:
    reply = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    ok("HTTP 200 + choices", f"reply='{reply.strip()}' | tokens(p={usage.get('prompt_tokens')},c={usage.get('completion_tokens')})")
else:
    fail("chat/completions", json.dumps(data, ensure_ascii=False)[:300])

# ======== Test 3: Chat stream ========
step(f"Test 3: POST /v1/chat/completions (stream SSE) [{TEST_MODEL}]")
try:
    req = urllib.request.Request(
        f"{API_BASE}/v1/chat/completions",
        data=json.dumps({"model": TEST_MODEL, "messages": [{"role": "user", "content": "One word reply"}], "stream": True}).encode("utf-8"),
        headers=HEADERS, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        lines = [l for l in raw.split("\n") if l.startswith("data:")]
        has_done = any("[DONE]" in l for l in lines)
        full = ""
        for l in lines:
            p = l[6:].strip()
            if p == "[DONE]":
                continue
            try:
                chunk = json.loads(p)
                d = chunk.get("choices", [{}])[0].get("delta", {})
                if "content" in d:
                    full += d["content"]
            except:
                pass
        ok("SSE stream", f"{len(lines)} events, [DONE]={'yes' if has_done else 'no'}, text='{full.strip()[:80]}'")
except Exception as e:
    fail("stream", str(e)[:200])

# ======== Test 4: Billing subscription ========
step("Test 4: GET /v1/dashboard/billing/subscription (Cursor verify)")
code, data = http("GET", "/v1/dashboard/billing/subscription")
if code == 200 and data.get("has_payment_method"):
    ok("HTTP 200 + has_payment_method=True", f"plan={data.get('plan',{}).get('title','N/A')}")
else:
    fail("billing/subscription", json.dumps(data, ensure_ascii=False)[:200])

# ======== Test 5: Billing usage ========
step("Test 5: GET /v1/dashboard/billing/usage")
code, data = http("GET", "/v1/dashboard/billing/usage")
if code == 200:
    ok("HTTP 200", f"total_usage={data.get('total_usage','N/A')} cents")
else:
    fail("billing/usage")

# ======== Test 6: OpenAI SDK ========
step("Test 6: OpenAI Python SDK")
try:
    import openai
    print(f"  [INFO]  openai SDK v{openai.__version__}")

    client = openai.OpenAI(base_url=f"{API_BASE}/v1", api_key=API_KEY, timeout=60)

    # models.list()
    models = client.models.list()
    ok("client.models.list()", f"{len(models.data)} models")

    # chat create non-stream
    resp = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "Reply exactly SDK_OK"}],
        temperature=0,
    )
    reply = resp.choices[0].message.content.strip()
    ok("client.chat.create() non-stream", f"reply='{reply[:40]}'")

    # chat create stream
    stream = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "Reply exactly STREAM_OK"}],
        temperature=0,
        stream=True,
    )
    collected = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            collected += chunk.choices[0].delta.content
    ok("client.chat.create() stream", f"reply='{collected.strip()[:40]}'")

except Exception as e:
    fail("OpenAI SDK", str(e)[:300])

# ======== Summary ========
print(f"\n{'='*60}")
print(f"  Results: {passed} passed, {failed} failed  ({passed}/{passed+failed})")
print(f"{'='*60}")
