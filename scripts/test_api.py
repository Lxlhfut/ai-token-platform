import json, urllib.request, urllib.error

# 测试 proxy 路由是否生效
tests = [
    ("GET", "http://localhost:8000/v1/models", "sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85"),
    ("POST", "http://localhost:8000/v1/chat/completions", "sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85"),
    # 也试一下带 / 结尾
    ("POST", "http://localhost:8000/v1/chat/completions/", "sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85"),
]

for method, url, key in tests:
    print(f"[{method}] {url}")
    body = json.dumps({"model":"qwen-turbo","messages":[{"role":"user","content":"hi"}]}).encode()
    req = urllib.request.Request(url, data=body if method=="POST" else None, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"  OK {r.status}: {r.read().decode()[:300]}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"  ERR: {e}")
    print()
