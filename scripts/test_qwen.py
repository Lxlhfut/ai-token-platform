"""
直接测试百炼上游千问模型是否可用
使用方法：双击运行，或在命令行执行：
  python test_qwen.py
"""
import json
import urllib.request
import urllib.error

API_KEY = "sk-ws-H.RPYPRRR.x2oB.MEQCIBcvXD-Y5dA3pHbKL_Z5OOrkeIcfj_bzEhJIsLGhqlRJAiAuGxov5zFKK_DLkZH7iPqAApEy5NzOe2RZgGIHdnD_1A"
BASE_URL = "https://ws-3wjvh4zw29cej56r.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

MODELS_TO_TEST = [
    "qwen-turbo",
    "qwen-plus",
    "qwen-max",
    "deepseek-v4-pro",
    "deepseek-v4-flash",
]

def test_model(model_name):
    url = f"{BASE_URL}/chat/completions"
    body = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": "请用一句话介绍你自己"}],
        "max_tokens": 50,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"  [OK]  {model_name}")
            print(f"        回复: {content[:80]}")
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")[:300]
        print(f"  [FAIL] {model_name}: HTTP {e.code}")
        print(f"        {err_body}")
        return False
    except Exception as e:
        print(f"  [ERR]  {model_name}: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("  测试百炼上游模型可用性")
    print(f"  Base URL : {BASE_URL}")
    print("=" * 60)
    print()

    results = {}
    for model in MODELS_TO_TEST:
        print(f"测试: {model}")
        results[model] = test_model(model)
        print()

    print("=" * 60)
    print("  汇总结果")
    print("=" * 60)
    for model, ok in results.items():
        status = "可用" if ok else "不可用"
        print(f"  {model:20s} -> {status}")
    print()
