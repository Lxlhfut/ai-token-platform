"""
平台千问模型诊断脚本
运行方式：在项目目录执行 python scripts\diagnose_qwen.py
"""
import urllib.request, urllib.error, json, sqlite3, os, sys

# 脚本在 scripts/ 目录下，db 在上层 data/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "data", "platform.db")
BASE = "http://localhost:8000"

# 用平台内的用户 API Key 测试
USER_API_KEY = "sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85"

print("=" * 60)
print("  平台千问通道诊断")
print("=" * 60)

# ===== 1. 检查渠道配置 =====
print("\n[1] 上游渠道配置")
conn = sqlite3.connect(DB_PATH)
for row in conn.execute("SELECT id, name, models, status, base_url FROM upstream_channels"):
    print(f"  id={row[0]}  {row[1]}  状态={row[3]}")
    print(f"    models={row[2]}")
    print(f"    base_url={row[4][:60]}...")

has_qwen_channel = False
for row in conn.execute("SELECT id, models FROM upstream_channels WHERE status='active'"):
    models_str = row[1] or ""
    models_list = [m.strip() for m in models_str.split(",")]
    if "qwen-turbo" in models_list or "qwen-plus" in models_list or "*" in models_str:
        has_qwen_channel = True
        print(f"  ✓ 渠道 {row[0]} 覆盖千问模型")

if not has_qwen_channel:
    print("  ✗ 没有渠道覆盖千问模型！请在管理后台编辑渠道，把 models 加上 qwen-turbo,qwen-plus,qwen-max")

# ===== 2. 检查定价 =====
print("\n[2] 模型定价")
qwen_pricing = {}
for row in conn.execute("SELECT model, input_price, output_price, is_active FROM model_pricing"):
    print(f"  {row[0]:30s} in={row[1]:>6.4f}  out={row[2]:>6.4f}  active={row[3]}")
    if row[0].startswith("qwen") and row[3]:
        qwen_pricing[row[0]] = True

for m in ["qwen-turbo", "qwen-plus", "qwen-max"]:
    if m not in qwen_pricing:
        print(f"  ⚠ {m} 无定价配置（会走'*'默认定价）")

conn.close()

# ===== 3. 测试平台代理 =====
print("\n[3] 通过平台调用测试")
for model in ["qwen-turbo", "qwen-plus", "deepseek-v4-pro"]:
    print(f"  测试 {model}...", end=" ")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 20,
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {USER_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"OK: {content[:60]}")
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:400]
        print(f"FAIL HTTP {e.code}")
        print(f"       {err}")
    except Exception as e:
        print(f"ERR: {e}")

print("\n" + "=" * 60)
print("  诊断完成")
print("=" * 60)
