import json, urllib.request, sys

url = "http://120.26.162.115/v1/chat/completions"
body = json.dumps({"model": "qwen-turbo", "messages": [{"role": "user", "content": "say hello"}]}).encode()
headers = {
    "Authorization": "Bearer sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85",
    "Content-Type": "application/json",
}

req = urllib.request.Request(url, data=body, headers=headers)
resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read())

print(f"Status: {resp.status}")
print(f"Model: {data.get('model')}")
# ASCII-safe output
reply = data["choices"][0]["message"]["content"]
usage = data.get("usage", {})
print(f"Reply: {reply.encode('ascii', 'replace').decode()}")
print(f"Tokens: prompt={usage.get('prompt_tokens')}, completion={usage.get('completion_tokens')}, total={usage.get('total_tokens')}")
