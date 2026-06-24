"""
Anthropic 兼容端点测试
用法: python scripts/test_anthropic.py
前提: 本地服务已启动 (uvicorn app.main:app)
"""
import json, sys, sqlite3, urllib.request, urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "platform.db"
BASE = "http://localhost:8000"
OK, FAIL, SKIP = "✅", "❌", "⚠️"


def req(method, path, body=None, headers=None):
    url = f"{BASE}{path}"
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            ct = resp.headers.get("Content-Type", "")
            raw = resp.read().decode()
            if "text/event-stream" in ct:
                return resp.status, raw
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def test(name):
    print(f"\n{'─'*50}\n  {name}\n{'─'*50}")
    return None


# ── 0. 从本地数据库拿 API Key ─────────────────────────────────
db = sqlite3.connect(str(DB_PATH))
db.row_factory = sqlite3.Row

usr = dict(db.execute("SELECT * FROM users WHERE balance > 0 LIMIT 1").fetchone())
key_row = db.execute("SELECT * FROM api_keys WHERE user_id = ? AND is_active = 1 LIMIT 1", (usr["id"],)).fetchone()
if not key_row:
    print("❌ 没有 API Key，请先去 dashboard 创建一个")
    sys.exit(1)
KEY = dict(key_row)["key"]

ch = db.execute("SELECT models FROM upstream_channels WHERE status = 'active' LIMIT 1").fetchone()
models = ch["models"].split(",")[0].strip() if ch else "deepseek-chat"
db.close()

print(f"用户: {usr['username']} | 余额: {usr['balance']} | 测试模型: {models}")

# ── 1. 非流式 Bearer Token ────────────────────────────────────
test("1) 非流式 /v1/messages — Bearer Token")
s, r = req("POST", "/v1/messages",
           {"model": models, "max_tokens": 50,
            "messages": [{"role": "user", "content": "say hello in 3 words"}]},
           {"Authorization": f"Bearer {KEY}"})

print(f"  status={s}")
if s == 200 and isinstance(r, dict):
    print(f"  {OK} type={r.get('type')}  role={r.get('role')}")
    txt = r.get("content", [{}])[0].get("text", "") if r.get("content") else ""
    print(f"  {OK} 回复: {txt[:60]}")
    print(f"  {OK} usage: {r.get('usage')}")
else:
    print(f"  {FAIL} {json.dumps(r, ensure_ascii=False)[:200]}")

# ── 2. 流式 /v1/messages ────────────────────────────────────────
test("2) 流式 /v1/messages (stream=true)")
s, raw = req("POST", "/v1/messages",
             {"model": models, "max_tokens": 50, "stream": True,
              "messages": [{"role": "user", "content": "say hello in 3 words"}]},
             {"Authorization": f"Bearer {KEY}"})

print(f"  status={s}")
if s == 200:
    has_msg_start = "message_start" in raw
    has_content = "content_block_delta" in raw
    has_msg_stop = "message_stop" in raw
    print(f"  {OK if has_msg_start else FAIL} message_start 事件")
    print(f"  {OK if has_content else FAIL} content_block_delta 事件")
    print(f"  {OK if has_msg_stop else FAIL} message_stop 事件")
    print(f"  SSE 总长度: {len(raw)} bytes, 事件数: {raw.count('event:')}")
else:
    print(f"  {FAIL} {raw[:200]}")

# ── 3. Token 计数端点 ───────────────────────────────────────────
test("3) /v1/messages/count_tokens")
s, r = req("POST", "/v1/messages/count_tokens",
           {"messages": [{"role": "user", "content": "Hello world! This is a test sentence."}]},
           {"Authorization": f"Bearer {KEY}"})

if s == 200 and isinstance(r, dict):
    print(f"  {OK} status=200 input_tokens={r.get('input_tokens')}")
else:
    print(f"  {FAIL} {r}")

# ── 4. x-api-key 认证 ────────────────────────────────────────────
test("4) x-api-key 认证方式")
s, r = req("POST", "/v1/messages",
           {"model": models, "max_tokens": 30,
            "messages": [{"role": "user", "content": "reply with just 'ok'"}]},
           {"x-api-key": KEY})

print(f"  {OK if s == 200 else FAIL} status={s}")

# ── 5. 原有 OpenAI 端点仍然工作 ──────────────────────────────────
test("5) 原有 /v1/chat/completions 不受影响")
s, r = req("POST", "/v1/chat/completions",
           {"model": models, "max_tokens": 30,
            "messages": [{"role": "user", "content": "reply with just 'ok'"}]},
           {"Authorization": f"Bearer {KEY}"})
ok = s == 200 and isinstance(r, dict) and r.get("choices")
print(f"  {OK if ok else FAIL} status={s} choices={'有' if ok else '无'}")

# ── 6. 错误处理 ──────────────────────────────────────────────────
test("6) 无效 API Key → Anthropic 格式错误")
s, r = req("POST", "/v1/messages",
           {"model": models, "max_tokens": 30, "messages": [{"role": "user", "content": "hi"}]},
           {"Authorization": "Bearer sk-invalid-key-xxx"})

if isinstance(r, dict):
    # Anthropic 错误可能直接在顶层，也可能被 FastAPI 包在 detail 里
    anthro_err = r.get("error") or r.get("detail", {}).get("error") or {}
    ok = bool(anthro_err.get("type"))
    print(f"  {OK if ok else FAIL} Anthropic 错误格式: {anthro_err}")
else:
    print(f"  {FAIL} {r}")

# ── 汇总 ─────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print("测试完成 — 非流式/流式/Token计数/双认证/向后兼容/错误处理 共 6 项")
print(f"{'='*50}")
