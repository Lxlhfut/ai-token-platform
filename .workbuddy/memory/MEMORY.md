# MEMORY.md - 项目长期记忆

## ai-token-platform 项目

**技术栈**：FastAPI + SQLAlchemy 2.0 (async) + SQLite + Jinja2 + 原生 JS
**入口**：`app/main.py`，`uvicorn app.main:app`，端口 8000

### 核心架构
- 用户中心：`/dashboard` → `dashboard.html` + `app.js initUserDashboard()`
- 管理后台：`/admin`（不在首页导航显示，需直接输入地址访问）
- API 代理：`/v1/chat/completions`，用 API Key 认证，自动扣费
- 计费逻辑：`app/services/billing.py`，`recharge_balance` / `deduct_balance`

### 用户认证（2026-06-24 更新）
- **用户名+密码登录**：username + password（已简化，删除所有手机/邮箱验证码方式）
- **用户名+密码注册**：username + password + 确认密码（两次一致）+ agreed_terms
- User 模型：email 改为 Optional，login/register 不再依赖 email
- 协议页面：`/terms`（用户注册协议）、`/privacy`（隐私政策）
- 前端认证面板 2 个 Tab：登录 / 注册，均有协议勾选框
- **管理员账号**：username=admin，密码见 `ADMIN_PASSWORD` 环境变量（默认 Admin123456!）
- 配置项从 `ADMIN_EMAIL` 改为 `ADMIN_USERNAME`，env.example / config.py / init_db.py 均已同步

### 充值机制（2026-06-22 改造后）
- **用户自助充值**：管理员在 `/admin` 生成兑换码（卡密），发给用户，用户在 `/dashboard` 输入兑换码充值
- 接口：`POST /api/user/redeem`（用户端）/ `POST /api/admin/redeem-codes`（管理端）
- 兑换码表：`redeem_codes`（code, amount, is_used, used_by, used_at）
- 旧手动充值接口 `/api/admin/recharge` 仍保留

### 关键文件
- `app/models.py` - 数据库模型（User, ApiKey, RedeemCode, UpstreamChannel, ModelPricing, UsageLog, Transaction）
- `app/routers/user.py` - 用户 API（用户名注册/登录/key 管理/兑换码充值）
- `app/routers/admin.py` - 管理 API（渠道/定价/用户/兑换码生成）
- `app/routers/proxy.py` - OpenAI 代理
- `app/static/app.js` - 前端全部交互逻辑（含 sendSmsCode 倒计时）
- `app/templates/terms.html` - 用户注册协议页面
- `app/templates/privacy.html` - 隐私政策页面
