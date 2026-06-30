"""
模型一致性验证脚本
用法: python scripts\verify_model.py deepseek-v4-pro
或者不传参数，先列出所有可用模型让你选。
"""
import urllib.request, urllib.error, json, sqlite3, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "data", "platform.db")
BASE = "http://localhost:8000"

def api(path, method="GET", body=None, headers=None):
    url = f"{BASE}{path}"
    hdrs = headers or {}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# ── 1. 确定目标模型 ──
target_model = sys.argv[1] if len(sys.argv) > 1 else None

# ── 2. 从数据库取定价和 API Key ──
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 倒序取最近登录的普通用户
cur.execute("""
    SELECT u.id, u.username, u.balance
    FROM users u WHERE u.is_active=1 AND u.role='user'
    ORDER BY u.id DESC LIMIT 1
""")
user_row = cur.fetchone()
if not user_row:
    print("❌ 没有普通用户，请先在平台注册一个测试账号")
    conn.close()
    sys.exit(1)

uid, uname, balance = user_row["id"], user_row["username"], user_row["balance"]

cur.execute("SELECT key FROM api_keys WHERE user_id=? AND is_active=1 LIMIT 1", (uid,))
key_row = cur.fetchone()
if not key_row:
    print(f"❌ 用户 {uname} 没有活跃 API Key")
    conn.close()
    sys.exit(1)

api_key = key_row["key"]

# ── 3. 查出所有可用模型（有定价 + 有渠道） ──
cur.execute("""
    SELECT DISTINCT mp.model, mp.input_price, mp.output_price
    FROM model_pricing mp
    WHERE mp.is_active=1 AND mp.model!='*'
      AND EXISTS (
        SELECT 1 FROM upstream_channels uc
        WHERE uc.status='active' AND (
          uc.models='*' OR
          ','||uc.models||',' LIKE '%,'||mp.model||',%'
        )
      )
    ORDER BY mp.model
""")
pricing_rows = cur.fetchall()
if not pricing_rows:
    print("❌ 当前没有任何可用的模型（需要定价 AND 渠道都到位）")
    conn.close()
    sys.exit(1)

pricing_map = {r["model"]: {"input": r["input_price"], "output": r["output_price"]} for r in pricing_rows}

if not target_model:
    print("可用的模型：")
    for i, r in enumerate(pricing_rows, 1):
        print(f"  {i}. {r['model']:30s}  in={r['input_price']:.4f}  out={r['output_price']:.4f}")

if target_model and target_model not in pricing_map:
    print(f"\n❌ 模型 {target_model} 不在可用列表中")
    print(f"   可用: {', '.join(pricing_map.keys())}")
    print(f"   请先确认：管理员后台已添加该模型的定价 AND 已有活跃渠道覆盖此模型")
    conn.close()
    sys.exit(1)

if not target_model:
    print(f"\n共 {len(pricing_rows)} 个模型，输入 ':all' 逐个测试，或输入编号/模型名：")
    choice = input("> ").strip()
    if choice == ":all":
        target_models = [r["model"] for r in pricing_rows]
    elif choice.isdigit():
        idx = int(choice) - 1
        target_models = [pricing_rows[idx]["model"]]
    else:
        target_models = [choice]
else:
    target_models = [target_model]

conn.close()

print(f"\n用户: {uname}  余额: ¥{balance:.4f}")
print(f"API Key: {api_key[:12]}...")
print("=" * 65)

# ── 4. 逐个模型测试 ──
all_ok = True
for model in target_models:
    pricing = pricing_map.get(model)
    print(f"\n▶ 测试模型: {model}")
    print(f"  定价: 输入 ¥{pricing['input']:.4f}/Ktokens  输出 ¥{pricing['output']:.4f}/Ktokens")

    body = {
        "model": model,
        "messages": [{"role": "user", "content": "只说一个字：好"}],
        "max_tokens": 5,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    status, resp = api("/v1/chat/completions", method="POST", body=body, headers=headers)

    if status != 200:
        err = resp.get("detail", str(resp))[:200]
        print(f"  ❌ HTTP {status}: {err}")
        all_ok = False
        continue

    # 验1: 返回里的 model 字段（注意：上游可能做模型别名映射，如 deepseek-chat→deepseek-v4-flash）
    # 这不影响计费——我们的平台按请求 model 定价和写日志
    resp_model = resp.get("model", "")
    if resp_model and resp_model != model:
        print(f"  ℹ️  上游返回 model={resp_model}（上游做了别名映射，平台计费仍按请求 model={model}）")
    elif resp_model:
        print(f"  ✅ 返回 model={resp_model}（与请求一致）")

    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = resp.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

    # 验2: 费用计算
    expected_cost = round((prompt_tokens / 1000) * pricing["input"] + (completion_tokens / 1000) * pricing["output"], 6)
    print(f"  tokens: prompt={prompt_tokens}  completion={completion_tokens}  total={total_tokens}")
    print(f"  预测费用: ¥{expected_cost:.6f}")

    # 验3: 查使用日志里的实际扣费
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    cur2 = conn2.cursor()
    cur2.execute("""
        SELECT cost, model, prompt_tokens, completion_tokens, status
        FROM usage_logs
        WHERE user_id=? AND status='success'
        ORDER BY id DESC LIMIT 1
    """, (uid,))
    log = cur2.fetchone()
    conn2.close()

    if log:
        log_model = log["model"]
        log_cost = log["cost"]
        print(f"  日志模型: {log_model}  |  实际扣费: ¥{log_cost:.6f}")

        # 验3a: 日志模型名一致
        if log_model == model:
            print(f"  ✅ 日志模型名一致")
        else:
            print(f"  ❌ 日志模型名不一致！{log_model} ≠ {model}")
            all_ok = False

        # 验3b: 扣费金额匹配
        if abs(log_cost - expected_cost) < 0.0001:
            print(f"  ✅ 扣费金额匹配预测")
        else:
            print(f"  ❌ 扣费不匹配！实际={log_cost:.6f}  预测={expected_cost:.6f}")
            all_ok = False
    else:
        print(f"  ⚠️  未找到使用日志记录")
        all_ok = False

print("\n" + "=" * 65)
if all_ok:
    print("✅ 全部通过：模型 → 渠道 → 上游 → 定价 → 扣费 全链路一致")
else:
    print("❌ 存在不一致项，请检查上方标记的 ❌ 项")
