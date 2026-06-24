# ai-token-platform API Key 多工具集成指南

## 测试验证结论

| 能力 | 状态 |
|------|:--:|
| `GET /v1/models` | ✅ 12 个模型 |
| `POST /v1/chat/completions` (非流式) | ✅ |
| `POST /v1/chat/completions` (流式 SSE) | ✅ |
| `GET /v1/dashboard/billing/subscription` | ✅ |
| `GET /v1/dashboard/billing/usage` | ✅ |
| openai SDK `models.list()` | ✅ |
| openai SDK `chat.completions.create()` non-stream | ✅ |
| openai SDK `chat.completions.create()` stream | ✅ |
| system prompt | ✅ |
| 多轮对话 | ✅ |

---

## 各工具兼容性总览

| 工具 | 是否可用 | 所需条件 |
|------|:--:|------|
| **Cursor IDE** | ✅ 可用 | **需要 HTTPS**（见下方 Cursor 部分） |
| **OpenAI Python SDK** | ✅ 可用 | 开箱即用 |
| **OpenAI Node.js SDK** | ✅ 可用 | 开箱即用 |
| **VS Code Copilot** | ⚠️ 部分 | Copilot 不支持自定义 endpoint，GitHub Copilot Chat 不行 |
| **VS Code + Continue/Cline 插件** | ✅ 可用 | 这些插件支持自定义 OpenAI endpoint |
| **Claude Desktop / SDK** | ❌ 不可用 | Claude 用 Anthropic 协议 (`/v1/messages`)，格式不同 |
| **Claude Code** | ❌ 不可用 | 同上，Anthropic 专用协议 |
| **OpenAI Codex** | ⚠️ | Codex 已退役，可用 qwen2.5-coder 替代 |
| **LobeChat / ChatBox** | ✅ 可用 | 支持自定义 OpenAI endpoint |
| **Aider / Cline / Roo Code** | ✅ 可用 | 支持自定义 OpenAI endpoint |

---

## 1. Cursor IDE 配置

### 问题：Cursor 要求 HTTPS

Cursor 不接受 `http://` 的自定义 API Base URL，必须用 `https://`。

### 解决方案（4 选 1）

#### 方案 A：部署到阿里云 ECS + Nginx（推荐，适合生产）
```
你的阿里云 ECS 已有公网 IP，直接部署即可：

# 1. SSH 登录 ECS
ssh root@<你的ECS公网IP>

# 2. 安装 nginx + certbot
apt update && apt install nginx certbot python3-certbot-nginx -y

# 3. 配置反向代理
cat > /etc/nginx/sites-enabled/api <<'EOF'
server {
    listen 80;
    server_name api.yourdomain.com;  # 改成你的域名
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
EOF

# 4. 获取 HTTPS 证书
certbot --nginx -d api.yourdomain.com

# 5. 部署项目
git clone <repo> /opt/ai-token-platform
cd /opt/ai-token-platform
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
```

#### 方案 B：Cloudflare Tunnel（免费，无需买域名）
```
# 1. 安装 cloudflared
# 下载: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel login

# 2. 创建 tunnel
cloudflared tunnel create ai-token
cloudflared tunnel route dns ai-token api.yourdomain.com

# 3. 运行
cloudflared tunnel run --url http://localhost:8000 ai-token
# 会得到一个 https://xxx.trycloudflare.com 地址
```

#### 方案 C：ngrok（快速测试）
```
ngrok http 8000
# 得到 https://xxxx.ngrok.io，填入 Cursor
```

#### 方案 D：本地开发用 Continue 插件（无需 HTTPS）
VS Code 装 **Continue** 插件，配置 `.continue/config.json`：
```json
{
  "models": [{
    "title": "qwen-turbo",
    "provider": "openai",
    "model": "qwen-turbo",
    "apiBase": "http://localhost:8000/v1",
    "apiKey": "sk-xxxx"
  }]
}
```

### Cursor 具体配置步骤（以方案 A/B/C 部署到 HTTPS 后）

1. 打开 Cursor → `Settings` → `Models`
2. 找到 `OpenAI API Key` 区域
3. 关闭 `Use Cursor API Key`
4. 填入：
   - **API Key**: `sk-xxxxxxxx`（你的平台 key）
   - **Base URL**: `https://api.yourdomain.com/v1`
5. Cursor 会自动调用 `/v1/models` 拉取模型列表
6. 在对话中选择你的模型即可

---

## 2. OpenAI Python SDK

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",   # 生产环境改成 https://api.xxx.com/v1
    api_key="sk-f70c1979d9386a3d73dd9cde5bd1a2fb4aa3b53b049a2f7c",
)

# 非流式
resp = client.chat.completions.create(
    model="qwen-turbo",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)

# 流式
stream = client.chat.completions.create(
    model="qwen-turbo",
    messages=[{"role": "user", "content": "写一段代码"}],
    stream=True,
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## 3. OpenAI Node.js SDK

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "sk-xxxx",
});

const resp = await client.chat.completions.create({
  model: "qwen-turbo",
  messages: [{ role: "user", content: "Hello" }],
});
console.log(resp.choices[0].message.content);
```

## 4. Claude 相关工具（Claude Desktop / Claude Code）

**不支持。** Claude 使用 Anthropic 原生协议（`POST /v1/messages`），而不是 OpenAI 格式（`POST /v1/chat/completions`）。你的平台目前只支持 OpenAI 兼容格式。

**如果你确实需要 Claude 模型**，有两个选择：
- **选择 A**：在平台中接入一个支持 Anthropic 格式的上游（如 OpenRouter），然后添加 `/v1/messages` 路由
- **选择 B**：用户直接使用 OpenAI 兼容的工具链（Cursor、Continue、Aider 等），不用 Claude 原生客户端

## 5. VS Code 扩展

### Continue (推荐)
```
.continue/config.json:
{
  "models": [
    {
      "title": "Qwen Turbo",
      "provider": "openai",
      "model": "qwen-turbo",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "sk-xxxx"
    }
  ]
}
```

### Cline / Roo Code
设置 → API Provider 选 "OpenAI Compatible" → 填入 Base URL 和 API Key

### GitHub Copilot
不支持自定义 endpoint，无法使用。

## 6. openai CLI

```bash
export OPENAI_API_KEY="sk-xxxx"
export OPENAI_BASE_URL="http://localhost:8000/v1"

# 或 Windows CMD:
set OPENAI_API_KEY=sk-xxxx
set OPENAI_BASE_URL=http://localhost:8000/v1

openai api chat.completions.create -m qwen-turbo -g user "你好"
```

---

## 测试脚本

项目自带两个测试脚本：

```bash
# 全面 HTTP 端点测试 (models + chat + stream + billing)
set API_KEY=sk-xxxx
python scripts/test_compat.py

# OpenAI SDK 深度测试 (models.list + chat.create + stream + system prompt + multi-turn)
python scripts/test_sdk.py
```
