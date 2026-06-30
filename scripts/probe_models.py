"""
上游模型探测脚本 — 扫描上游 API Key 支持哪些模型

用法:
  python scripts\probe_models.py <base_url> <api_key>

示例:
  python scripts\probe_models.py https://api.deepseek.com/v1 sk-xxxxx
  python scripts\probe_models.py https://ws-xxx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1 sk-ws-xxxxx
"""
import json, sys, urllib.request, urllib.error

# 候选模型列表（覆盖主流厂商）
CANDIDATES = [
    # OpenAI
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo",
    # 千问
    "qwen-turbo", "qwen-plus", "qwen-max", "qwen-max-longcontext",
    "qwen2.5-72b-instruct", "qwen2.5-32b-instruct", "qwen2.5-14b-instruct",
    "qwen2.5-7b-instruct", "qwq-32b", "qwen3-235b-a22b",
    # DeepSeek
    "deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro", "deepseek-v4-flash",
    # 百川
    "baichuan4", "baichuan3-turbo",
    # 智谱
    "glm-4", "glm-4-plus", "glm-4-flash",
    # 月之暗面
    "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k",
    # 零一万物
    "yi-large", "yi-medium", "yi-spark",
    # 百炼百应
    "bailian-vl-plus",
    # 其他
    "llama3-70b", "llama3-8b", "mixtral-8x7b",
]

TIMEOUT = 20

def test_model(base_url: str, api_key: str, model: str) -> tuple[bool, str]:
    """返回 (是否可用, 回复摘要或错误信息)"""
    url = f"{base_url.rstrip('/')}/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "1+1=?"}],
        "max_tokens": 10,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "<空回复>")
            return True, content[:60]
    except urllib.error.HTTPError as e:
        err_text = e.read().decode("utf-8")[:200]
        # 尝试提取上游错误消息
        try:
            err_json = json.loads(err_text)
            msg = err_json.get("error", {}).get("message", err_text)
        except json.JSONDecodeError:
            msg = err_text
        return False, f"HTTP {e.code}: {msg}"
    except Exception as e:
        return False, str(e)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    base_url = sys.argv[1]
    api_key = sys.argv[2]

    print(f"Base URL : {base_url}")
    print(f"API Key  : {api_key[:16]}...{api_key[-4:]}")
    print("=" * 60)
    print()

    available = []
    unavailable = []

    for i, model in enumerate(CANDIDATES):
        print(f"[{i+1:>2}/{len(CANDIDATES)}] {model:35s} ", end="", flush=True)
        ok, detail = test_model(base_url, api_key, model)
        if ok:
            print(f"✓ 可用   {detail}")
            available.append((model, detail))
        else:
            # 区分"模型不存在"和其他错误
            is_model_error = any(kw in detail.lower() for kw in
                ["not support", "not found", "invalid", "不支持", "not available", "does not exist"])
            if is_model_error:
                print(f"✗ 不支持")
            else:
                print(f"✗ {detail[:60]}")
            unavailable.append((model, detail))

    print()
    print("=" * 60)
    print(f"  可用模型: {len(available)} / {len(CANDIDATES)}")
    print("=" * 60)

    if available:
        print("\n✅ 可用模型列表:")
        for model, reply in available:
            print(f"    {model}")
        print()

        # 输出可直接粘贴到渠道 models 字段的格式
        print("📋 渠道 models 字段（可直接复制）:")
        print(f"    {','.join(m for m, _ in available)}")

    if unavailable:
        print(f"\n❌ 不可用: {len(unavailable)} 个（多数是因为该厂商不提供此模型）")


if __name__ == "__main__":
    main()
