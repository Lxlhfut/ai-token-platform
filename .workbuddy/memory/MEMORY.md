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

### Anthropic 兼容端点（2026-06-24 新增）
- `/v1/messages` — Anthropic 原生格式（支持 Claude Code / Claude Desktop）
- `/v1/messages/count_tokens` — Anthropic token 计数
- 认证：支持 `x-api-key` 和 `Authorization: Bearer` 两种方式
- 适配器：`app/services/anthropic_adapter.py`（Anthropic ↔ OpenAI 双向转换）
- 错误响应：用 `JSONResponse` 直接返回避免 FastAPI 包 `{"detail": ...}`

### 推理模型注意事项
- `deepseek-v4-pro` 是推理模型（类似 DeepSeek-R1），思考占 ~80% token，实际回答占 ~20%
- **必须给足够 max_tokens（建议 ≥1024）**，否则 content 为空（token 全被推理消耗）
- 上游返回 `reasoning_content` 字段存放推理过程，content 是最终回答

### 管理后台「分组管理」「降级映射」「毛利报告」（2026-06-29 新增）
- **新表**：`model_groups`（模型分组：id, name, description, is_default, created_at）、`model_fallbacks`（降级映射：id, source_model, target_model, priority, is_active, created_at）
- **ModelPricing 新增字段**：`cost_price`（上游成本价，元/1K tokens，用于毛利计算）、`created_at`
- **管理端 API**：
  - `GET/POST /api/admin/groups`、`PUT/DELETE /api/admin/groups/{id}`、`POST /api/admin/groups/{id}/default` — 分组 CRUD + 设默认
  - `GET/POST /api/admin/fallbacks`、`PUT/DELETE /api/admin/fallbacks/{id}` — 降级映射 CRUD
  - `GET /api/admin/pricing/margin` — 毛利报告（按分组汇总成本/售价/利润 + 模型明细表，近30天数据）
- **前端（admin.html + app.js）**：
  - 侧边栏新增「分组管理」「降级映射」「毛利报告」三个入口
  - app.js 实现完整 CRUD 函数 + loadMarginReport（含总览卡片、分组汇总、明细表格）
  - 定价管理表单增加「上游成本价」字段，列表展示成本信息
- **数据库迁移**：`app/init_db.py` 新增 `_add_column_if_missing` 通用迁移辅助函数
- **数据库路径修复**：`app/database.py` 将相对 SQLite 路径解析为项目根目录绝对路径
- **用户端定价独立**：`dashboard.html` 侧边栏新增「模型定价」入口，`pane-pricing` 标签页独立展示定价表

### 关键文件（更新）
- `app/models.py` - 数据库模型（新增 ModelGroup, ModelFallback；ModelPricing 新增 cost_price/created_at）
- `app/schemas.py` - Pydantic 数据模型（新增分组/降级/毛利报告 Schema）
- `app/routers/admin.py` - 管理 API（新增分组管理、降级映射、毛利报告端点）
- `app/init_db.py` - 数据库初始化与迁移（新增 `_add_column_if_missing` 通用迁移辅助函数）
- `app/database.py` - 数据库连接（新增 SQLite 路径绝对化处理）
- `app/static/app.js` - 前端交互逻辑（新增分组/降级/毛利报告全套函数）
- `app/templates/admin.html` - 管理后台页面（新增分组/降级映射/毛利报告侧边栏和标签页）
- `app/templates/dashboard.html` - 用户中心页面（新增模型定价独立标签页）

### 代理系统（2026-06-25 新增/更新）
- **新表**：`agents`（代理信息）、`agent_commissions`（佣金明细）、`agent_withdrawals`（提现申请）
- **User 新增字段**：`referrer_agent_id`（逻辑外键，记录邀请注册的代理ID）
- **佣金比例**：被邀请用户每次充值，代理获得 80%，平台获得 20%
- **提现方式**：代理申请提现到本人微信/支付宝，需上传收款码图片（PNG/JPG，≤2MB）；管理员通过收款码手动打款后在后台点「已打款」确认；拒绝时冻结佣金自动退回
- **用户端 API**：
  - `POST /api/user/agent/apply` — 申请成为代理
  - `GET /api/user/agent/info` — 获取代理信息（邀请码、佣金统计）
  - `GET /api/user/agent/commissions` — 佣金明细（只显示我的佣金，不显示充值金额）
  - `POST /api/user/agent/withdraw` — 提交提现申请（预扣佣金冻结，等管理员打款）
  - `GET /api/user/agent/withdrawals` — 提现历史
- **管理端 API**：
  - `GET /api/admin/agents` — 代理列表
  - `POST /api/admin/agents/{id}/approve` — 审批通过（自动生成邀请码）
  - `POST /api/admin/agents/{id}/reject` — 拒绝
  - `POST /api/admin/agents/{id}/disable` — 禁用/恢复切换
  - `GET /api/admin/agents/{id}/commissions` — 代理佣金明细
  - `GET /api/admin/agent-withdrawals` — 所有提现申请
  - `POST /api/admin/agent-withdrawals/{id}/complete` — 确认已打款
  - `POST /api/admin/agent-withdrawals/{id}/reject` — 拒绝（退回佣金）
- **注册邀请码**：注册表单有可选邀请码字段；URL 参数 `?ref=CODE` 自动填入
- **数据库迁移**：`init_db.py` 中 `_run_migrations` 自动给 users 表添加 referrer_agent_id 列；agent_withdrawals 由 create_all 自动创建
- **循环外键处理**：referrer_agent_id 使用普通 Integer 列（不用 ForeignKey），避免 SQLite create_all 循环依赖

### 固定金额扫码充值 + 管理员审核（2026-06-25 新增）
**方案**：用户选择固定面额（2/5/10/20/50/100/500）→ 展示对应收款码 → 扫码支付 → 管理员核对账单后确认到账。无需微信/支付宝 API，用个人 app 生成固定金额收款码即可。

- **订单状态**：`pending`（已创建）→ `submitted`（用户已提交，待审核）→ `paid`（管理员确认到账）/ `cancelled`（拒绝）
- **平台收款码**：`platform_qrcodes` 表，每个 (pay_method, amount) 对应一张收款码图片
- **关键接口**：
  - `POST /api/admin/platform-qrcode` — 上传收款码（Form: pay_method + amount + file）
  - `POST /api/admin/recharge-orders/{id}/verify` — 审核订单（approve/reject，approve 自动调用 recharge_balance）
  - `GET /api/platform-qrcodes` — 公开接口，用户端获取收款码
- **管理员通知**：`new_recharge_order` 类型，点击跳转到订单页审核
