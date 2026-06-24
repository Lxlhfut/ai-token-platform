# AI Token 中转站 — 部署指南

> 基于 FastAPI 的 OpenAI 兼容 API 中转与 Token 计费平台。

---

## 前置准备

| 项目 | 要求 |
|------|------|
| 服务器 | 1 核 1G 以上，Linux（Ubuntu 20.04+ / Debian 11+ / CentOS 8+） |
| 软件 | Docker 24+ + Docker Compose v2 |
| 域名 | 已备案，DNS 解析到服务器 IP |
| 端口 | 80 / 443 公网可达（用于 Nginx/Caddy 反向代理） |
| 上游 API | OpenAI / Anthropic / DeepSeek 等至少一个上游 API Key |

---

## 第一步：服务器基础环境

```bash
# 安装 Docker（以 Ubuntu 为例）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 验证
docker --version
docker compose version
```

---

## 第二步：上传项目到服务器

```bash
# 方式 A：git clone（推荐）
git clone <你的仓库地址> /opt/ai-token-platform
cd /opt/ai-token-platform

# 方式 B：rsync 从本地上传
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  ./ai-token-platform/ root@<服务器IP>:/opt/ai-token-platform/
```

---

## 第三步：配置环境变量

```bash
# 从模板创建 .env
cp env.example .env

# 生成安全的 SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# 把输出复制到下方
```

编辑 `.env`：

```ini
SECRET_KEY=<上一步生成的安全随机字符串>
DATABASE_URL=sqlite+aiosqlite:///./data/platform.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<你的管理员密码，务必修改默认值>
PLATFORM_NAME=AI Token 中转站
CURRENCY=CNY
UPSTREAM_TIMEOUT=120
ALLOW_REGISTRATION=true
RECHARGE_NOTICE=使用兑换码（卡密）即可自助充值，在下方「充值余额」框中输入兑换码，充值后余额立即到账，即可按量调用 AI 模型。
```

> ⚠️ **务必修改 `SECRET_KEY` 和 `ADMIN_PASSWORD`，不要用默认值！**

---

## 第四步：启动服务

```bash
docker compose up -d --build
```

验证：

```bash
# 检查容器运行状态
docker compose ps

# 检查健康接口
curl http://localhost:8000/health
# 返回 {"status":"ok","platform":"AI Token 中转站"}

# 查看日志（如启动异常）
docker compose logs -f
```

首次启动会自动：
- 创建 `data/` 目录和 SQLite 数据库
- 初始化管理员账号（用户名/密码来自 `.env`）
- 创建 5 条默认模型定价（gpt-4o / gpt-4o-mini / gpt-3.5-turbo / claude-3-5-sonnet / deepseek-chat）

---

## 第五步：配置反向代理（Nginx + HTTPS）

### 5.1 安装 Nginx 和 Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 5.2 Nginx 配置

创建 `/etc/nginx/sites-available/ai-token`：

```nginx
server {
    listen 80;
    server_name <你的域名>;

    # 代理 WebSocket（流式传输需要）
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;        # 流式长连接
        proxy_buffering off;            # 关闭缓冲确保 SSE 实时推送
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/ai-token /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5.3 申请 SSL 证书

```bash
sudo certbot --nginx -d <你的域名>
# 按提示操作，选择自动重定向 HTTP → HTTPS
```

验证 HTTPS：浏览器打开 `https://<你的域名>/`，应当看到首页。

---

## 第六步：首次管理后台配置

### 6.1 登录管理后台

浏览器打开 `https://<你的域名>/admin`，用 `.env` 中设置的管理员账号密码登录。

### 6.2 添加上游渠道

进入「上游渠道」→「添加渠道」：

| 字段 | 填写内容 |
|------|---------|
| 名称 | 如 `OpenAI 官方` / `DeepSeek 官方` |
| Base URL | `https://api.openai.com` 或 `https://api.deepseek.com` |
| API Key | 你的上游 API Key |
| 模型列表 | 每行一个，如 `gpt-4o` / `deepseek-chat` |

> **添加渠道后，系统会自动为填写的模型创建默认定价**（输入 ¥0.002 / 千 token，输出 ¥0.006 / 千 token）。

### 6.3 调整定价

进入「定价管理」，修改每个模型的输入/输出单价：

| 模型 | 建议输入价 (¥/千token) | 建议输出价 (¥/千token) |
|------|----------------------|----------------------|
| gpt-4o | 0.015 | 0.06 |
| gpt-4o-mini | 0.001 | 0.004 |
| deepseek-chat | 0.001 | 0.002 |
| claude-3-5-sonnet | 0.018 | 0.09 |

> 定价逻辑：`(总 token / 1000) × 对应单价`，在官方价格基础上适当溢价赚取差价。

---

## 第七步：验证完整链路

### 7.1 注册普通用户

1. 打开 `https://<你的域名>/dashboard`
2. 切换到「注册」Tab
3. 填写用户名 + 密码，勾选协议，提交

### 7.2 生成兑换码充值

1. 回到管理后台 `/admin` →「兑换码」→「生成兑换码」
2. 填写金额（如 10 元）和数量，生成
3. 复制兑换码
4. 回到 `/dashboard`，在「充值余额」框粘贴兑换码，提交
5. 余额立即到账

### 7.3 API 调用测试

```bash
# 非流式
curl https://<你的域名>/v1/chat/completions \
  -H "Authorization: Bearer <用户API Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'

# 流式（SSE）
curl https://<你的域名>/v1/chat/completions \
  -H "Authorization: Bearer <用户API Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

### 7.4 客户端配置

在 Cursor / Cherry Studio / LobeChat 等客户端中：

- **Base URL / API Base**：`https://<你的域名>/v1`
- **API Key**：在 `/dashboard` 页面创建的 Key

---

## 常用运维命令

```bash
# 查看日志
docker compose logs -f web

# 重启服务
docker compose restart

# 更新后重建
git pull
docker compose up -d --build

# 备份数据库
cp data/platform.db data/platform.db.$(date +%Y%m%d).bak

# 停止服务
docker compose down
```

---

## 故障排查

| 现象 | 排查步骤 |
|------|---------|
| 启动失败 | `docker compose logs web` 查看报错 |
| 502 Bad Gateway | Nginx 能否 curl 到 localhost:8000 |
| 余额不足 | 检查兑换码是否已使用，用户余额是否够用 |
| 上游不可用 | 检查上游 API Key 是否有效、Base URL 是否正确 |
| 流式中断 | 确认 Nginx `proxy_buffering off;` 已设置 |
| 模型不可用 | 检查上游渠道中是否填写了该模型，且在定价管理中已定价 |

---

## 安全建议

1. **SECRET_KEY 必须修改**：生产环境用 `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` 生成
2. **ADMIN_PASSWORD 必须修改**：不要用 Admin123456!
3. **定期备份数据库**：`data/platform.db` 包含所有用户、余额、记录
4. **防火墙**：仅开放 80/443，8000 端口不要公网暴露
5. **fail2ban**：建议对 Nginx 启用 fail2ban 防止暴力破解
6. **ALLOW_REGISTRATION=false**：用户量稳定后可关闭公开注册
