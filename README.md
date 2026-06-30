# AI Token 中转销售平台

基于 FastAPI 的 OpenAI 兼容 API 中转与 Token 计费平台。

## 本地运行

1. `copy env.example .env`
2. `pip install -r requirements.txt`
3. `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

<<<<<<< HEAD
访问：http://127.0.0.1:8000/ （用户中心 `/dashboard`）
=======
访问：http://127.0.0.1:8000/ （用户中心 `/dashboard`，管理后台 `/admin`）
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03

## Docker

```
docker compose up -d --build
```

## 部署需提供的信息

- **SECRET_KEY**：JWT 密钥（生产环境随机长字符串）
- **DATABASE_URL**：SQLite 或 PostgreSQL 连接串
- **ADMIN_USERNAME / ADMIN_PASSWORD**：首次启动创建的管理员账号和密码
- **上游渠道**（管理后台）：Base URL、上游 API Key、支持模型
- **公网域名 + HTTPS 反向代理**（Nginx/Caddy 转发到 8000）

客户端 `base_url` 设为 `https://您的域名/v1`，`api_key` 使用本平台生成的 Key。

## 默认管理员

见 `env.example` 中 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD`。