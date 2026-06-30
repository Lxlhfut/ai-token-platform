"""
端到端验证：用户选模型 → 渠道 → 定价 → 扣费 → 上游 → 日志
"""
import urllib.request, urllib.error, json, sqlite3, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "data", "platform.db")
BASE = "http://localhost:8000"

def api(path, method="GET", body=None, headers=None):
    url = f"{BASE}{path}"
    if headers is None:
        headers = {}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def db_query(query):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return rows

print("=" * 60)
print("  模型→定价→扣费 全链路验证")
print("=" * 60)

# ─────────── 1. 获取可用模型 ───────────
print("\n[1] 获取可用模型 (/v1/models)")
status, data = api("/v1/models", headers={"Authorization": "Bearer sk-demo"})
if status == 200:
    models = [m["id"] for m in data.get("data", [])]
    print(f"  平台暴露 {len(models)} 个模型: {', '.join(models)}")
else:
    print(f"  FAIL: {status} {data}")
    models = []

# ─────────── 2. 检查定价配置 ───────────
print("\n[2] 检查定价配置")
pricing_rows = db_query("SELECT model, input_price, output_price, is_active FROM model_pricing ORDER BY model")
pricing_map = {}
for m, inp, out, active in pricing_rows:
    pricing_map[m] = {"input": inp, "output": out, "active": active}
    status_str = "✓" if active else "✗"
    print(f"  {status_str} {m:30s} in={inp:>8.4f}  out={out:>8.4f}")

# ─────────── 3. 检查渠道覆盖 ───────────
print("\n[3] 检查渠道→模型映射")
channel_rows = db_query("SELECT id, name, models, status, weight FROM upstream_channels")
for cid, name, models_str, status, weight in channel_rows:
    if status != "active":
        continue
    models_list = [m.strip() for m in models_str.split(",") if m.strip()]
    if models_str.strip() == "*":
        models_list = ["* (通配，覆盖所有)"]
    print(f"  渠道 #{cid} {name:20s} weight={weight} models={models_str}")

# ─────────── 4. 获取测试用户的 API Key ───────────
print("\n[4] 获取测试 API Key")
user_rows = db_query("SELECT u.id, u.username, u.balance FROM users u WHERE u.is_active=1 AND u.role='user' LIMIT 1")
if not user_rows:
    print("  ⚠ 无普通用户，跳过 API 测试。请先注册一个测试用户。")
    sys.exit(0)

uid, uname, balance = user_rows[0]
print(f"  测试用户: {uname} (余额: {balance})")

key_rows = db_query(f"SELECT key, is_active FROM api_keys WHERE user_id={uid} AND is_active=1 LIMIT 1")
if not key_rows:
    print(f"  ⚠ 用户 {uname} 没有活跃 API Key，跳过 API 测试。")
    sys.exit(0)

api_key = key_rows[0][0]
print(f"  API Key: {api_key[:12]}...")

# ─────────── 5. 逐个模型做 API 调用测试 ───────────
print("\n[5] 逐个模型 API 调用测试")
print("-" * 60)

results = []
for model in models[:5]:  # 只测前5个，避免费太多钱
    print(f"  测试: {model}...", end=" ", flush=True)
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "回复一个字：好"}],
        "max_tokens": 5,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    status, resp = api("/v1/chat/completions", method="POST", body=body, headers=headers)
    if status == 200:
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")[:30]
        usage = resp.get("usage", {})
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        print(f"✓ 回复={content!r:20s} prompt={pt} completion={ct}")
        results.append((model, True, pt, ct))
    else:
        err = resp.get("detail", str(resp))[:120]
        print(f"✗ HTTP {status}: {err}")
        results.append((model, False, 0, 0))

# ─────────── 6. 检查使用日志 ───────────
print("\n[6] 检查使用日志（最近 10 条）")
log_rows = db_query("""
    SELECT ul.model, ul.prompt_tokens, ul.completion_tokens, ul.cost, ul.status, u.username
    FROM usage_log ul
    JOIN users u ON u.id = ul.user_id
    ORDER BY ul.created_at DESC LIMIT 10
""")
print(f"  {'模型':<25s} {'prompt':>7s} {'compl':>7s} {'费用':>10s} {'状态':>8s} {'用户':<12s}")
print("  " + "-" * 75)
for model, pt, ct, cost, status, uname in log_rows:
    print(f"  {model:<25s} {pt:>7d} {ct:>7d} {cost:>10.6f} {status:>8s} {uname:<12s}")

# ─────────── 7. 定价匹配检查 ───────────
print("\n[7] 定价匹配检查")
for model, ok, pt, ct in results:
    if not ok:
        continue
    pricing = pricing_map.get(model)
    if not pricing:
        pricing = pricing_map.get("*")
    if pricing:
        expected = round((pt / 1000) * pricing["input"] + (ct / 1000) * pricing["output"], 6)
        # 查实际扣费
        log_rows2 = db_query(f"""
            SELECT cost FROM usage_log
            WHERE model='{model}' AND user_id={uid} AND status='success'
            ORDER BY created_at DESC LIMIT 1
        """)
        actual = log_rows2[0][0] if log_rows2 else 0
        match = "✓" if abs(expected - actual) < 0.001 else "✗"
        print(f"  {model:25s} 预测={expected:.6f}  实际={actual:.6f}  {match}")

print("\n" + "=" * 60)
print("  验证完成")
print("=" * 60)
