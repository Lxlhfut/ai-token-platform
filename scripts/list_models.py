#!/usr/bin/env python3
"""
查询 OpenAI 风格 API 的模型列表
用法:
    python list_models.py --key sk-xxxxx --baseurl https://api.example.com/v1
"""

import argparse
import json
import sys
import requests
from urllib.parse import urljoin


def fetch_models(api_key: str, base_url: str) -> list:
    """
    向 {base_url}/models 发送 GET 请求，返回模型 ID 列表。
    """
    base_url = base_url.rstrip('/')
    endpoint = urljoin(base_url + '/', 'models')

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 兼容 OpenAI 格式: {"data":[{"id":"..."}]}
        if "data" in data and isinstance(data["data"], list):
            models = [item.get("id") for item in data["data"] if item.get("id")]
        else:
            # 兼容其他可能的返回格式
            if isinstance(data, list):
                models = [str(item) for item in data]
            elif isinstance(data, dict):
                if "models" in data:
                    models = data["models"]
                else:
                    models = list(data.keys())
            else:
                models = []
        return models
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应内容: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("响应不是有效的 JSON", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="列出 API 支持的模型")
    parser.add_argument("--key", help="API Key (以 sk- 开头)")
    parser.add_argument("--baseurl", help="API Base URL (例如: https://api.openai.com/v1)")
    args = parser.parse_args()

    # 获取 API Key（若无参数则交互输入）
    api_key = args.key
    if not api_key:
        api_key = input("请输入 API Key (sk-...): ").strip()
        if not api_key:
            print("错误: 未提供 API Key", file=sys.stderr)
            sys.exit(1)

    if not api_key.startswith("sk-"):
        print("警告: API Key 不以 'sk-' 开头，请确认是否正确", file=sys.stderr)

    # 获取 Base URL（若无参数则交互输入，且不允许为空）
    base_url = args.baseurl
    if not base_url:
        base_url = input("请输入 Base URL (例如: https://api.openai.com/v1): ").strip()
        if not base_url:
            print("错误: 未提供 Base URL", file=sys.stderr)
            sys.exit(1)

    print(f"正在查询模型列表: {base_url}/models", file=sys.stderr)

    models = fetch_models(api_key, base_url)

    if not models:
        print("未获取到任何模型")
    else:
        print("\n支持的模型列表:")
        for model in models:
            print(f"  - {model}")

        print(f"\n共 {len(models)} 个模型")


if __name__ == "__main__":
    main()