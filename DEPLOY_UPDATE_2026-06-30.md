# 部署更新教程 - 2026-06-30

> **本次更新内容**：模型定价标签系统、API Key 模型绑定、底部固定 ICP 备案号、任意金额充值
> **目标服务器**：root@120.26.162.115 (ylxunlapi.top)

---

## 方式一：SCP 上传（推荐，简单可靠）

### 1. 在本地 PowerShell 中执行

```powershell
# 进入项目根目录
cd e:\ai-token-platform-main

# 上传所有变更文件（保留目录结构）
scp `
  app/templates/dashboard.html `
  app/templates/admin.html `
  app/static/app.js `
  app/static/style.css `
  app/models.py `
  app/schemas.py `
  app/init_db.py `
  app/routers/user.py `
  app/routers/admin.py `
  .env `
  root@120.26.162.115:/opt/ai-token-platform/
```

> **注意**：如果 `.env` 文件中有敏感信息（API Key、支付宝凭证等），确认服务器上已有最新配置后再上传。

### 2. 在服务器上重启服务

```bash
# SSH 登录服务器
ssh root@120.26.162.115

# 进入项目目录
cd /opt/ai-token-platform

# 重启 Docker 容器（自动重建镜像）
docker compose up -d --build

# 查看日志确认启动成功
docker compose logs -f web
```

看到以下日志表示启动成功：
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

按 `Ctrl+C` 退出日志查看。

---

## 方式二：rsync 同步（适合频繁更新）

### 1. 安装 rsync（Windows）

如果你用的是 Git Bash 或 WSL，rsync 通常已安装。否则可以使用以下方式：

**方式 A：使用 Git Bash**
```bash
# Git Bash 自带 rsync
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  ./app/templates/dashboard.html ./app/templates/admin.html ./app/static/app.js ./app/static/style.css ./app/models.py ./app/schemas.py ./app/init_db.py ./app/routers/user.py ./app/routers/admin.py ./app/config.py ./app/routers/admin.py \
  root@120.26.162.115:/opt/ai-token-platform/
```

**方式 B：使用 PowerShell + pscp（WinSCP 工具）**

下载 WinSCP：https://winscp.net/
- 安装后打开，输入服务器信息：
  - 主机：`120.26.162.115`
  - 用户名：`root`
  - 密码：你的服务器密码
- 左侧本地目录：`E:\ai-token-platform-main`
- 右侧远程目录：`/opt/ai-token-platform`
- 拖拽上传变更文件

---

## 方式三：Git 拉取（如果有代码仓库）

```bash
# SSH 登录服务器
ssh root@120.26.162.115

# 进入项目目录
cd /opt/ai-token-platform

# 拉取最新代码
git pull origin main

# 重启服务
docker compose up -d --build

# 查看日志
docker compose logs -f web
```

---

## 验证更新

### 1. 检查服务状态

```bash
# 查看容器状态
docker compose ps

# 应显示：
# NAME                    STATUS
# ai-token-platform-web-1   Up (healthy)
```

### 2. 检查健康接口

```bash
curl http://localhost:8000/health
# 返回：{"status":"ok","platform":"AI Token Platform"}
```

### 3. 浏览器验证

访问 https://ylxunlapi.top/dashboard

- [ ] 底部固定显示 ICP 备案号（琼ICP备2026009208号）
- [ ] 模型定价页面有搜索框、排序、系列筛选 chips
- [ ] API Key 管理页面可以点击「创建新 Key」弹出表单
- [ ] 点击「编辑」可以修改 API Key 并绑定模型
- [ ] 充值页面支持任意金额输入

---

## 回滚方案

如果更新后出现问题，可以快速回滚：

```bash
# SSH 登录服务器
ssh root@120.26.162.115

# 停止服务
cd /opt/ai-token-platform
docker compose down

# 重新上传旧版本文件（从备份）
# 或使用 git 回退
git reset --hard HEAD~1
git pull  # 如果有远程仓库

# 重新启动
docker compose up -d --build
```

---

## 常见问题

### Q1: 上传后页面没有变化？

**原因**：浏览器缓存了旧版 JS/CSS 文件

**解决**：
- 按 `Ctrl+F5` 强制刷新
- 或在浏览器开发者工具（F12）→ Network → 勾选 "Disable cache"

### Q2: Docker 启动失败？

**查看日志**：
```bash
docker compose logs web
```

**常见错误**：
- `database is locked` → 检查 SQLite 文件权限
- `port 8000 already in use` → `docker compose down` 后重试
- `module not found` → 检查 `requirements.txt` 是否完整

### Q3: 数据库迁移失败？

服务启动时会自动执行迁移（`init_db.py` 中的 `_run_migrations`），新增列不会丢失数据。

如果需要手动检查：
```bash
# 进入数据库查看
docker exec -it ai-token-platform-web-1 python -c "
import sqlite3
conn = sqlite3.connect('/opt/ai-token-platform/data/platform.db')
cursor = conn.execute('PRAGMA table_info(api_keys)')
for row in cursor:
    print(row)
"
```

---

## 本次更新的文件清单

| 文件 | 变更说明 |
|------|---------|
| `app/templates/dashboard.html` | 添加 API Key 模态框、底部 ICP 备案号、模型定价搜索/排序/筛选 UI |
| `app/templates/admin.html` | 添加底部 ICP 备案号 |
| `app/static/app.js` | 新增标签系统、API Key 模型绑定、定价搜索/排序/筛选、ICP footer |
| `app/static/style.css` | 新增标签徽章、API Key 表单、ICP 固定底部样式 |
| `app/models.py` | ApiKey 新增 `allowed_models` 列 |
| `app/schemas.py` | ApiKey/ModelPricing 新增 tags/allowed_models 字段及 validator |
| `app/init_db.py` | 自动迁移 `tags` 和 `allowed_models` 列 |
| `app/routers/user.py` | 新增 PUT /api-keys/{id} 路由，处理 allowed_models 序列化 |
| `app/routers/admin.py` | create/update_pricing 处理 tags 序列化 |

---

## 部署后检查清单

- [ ] 首页底部显示 ICP 备案号（固定定位）
- [ ] 用户中心 → 模型定价：搜索框可用、排序下拉可用、系列 chips 可点击
- [ ] 用户中心 → API Key：点击「创建新 Key」弹出模态框
- [ ] API Key 模态框：模型分组选择器正常、全选/清空/预览功能正常
- [ ] 编辑 API Key：已选模型正确回显
- [ ] 充值页面：任意金额输入正常、快捷预设按钮正常
- [ ] 管理后台 → 定价管理：编辑时可设置标签
- [ ] 数据库：`model_pricing.tags` 和 `api_keys.allowed_models` 列已创建

---

**部署完成后，建议立即检查：**
1. 浏览器无痕模式访问 https://ylxunlapi.top/dashboard 确认无缓存问题
2. 测试创建 API Key 并绑定模型，验证功能正常
3. 测试模型定价页面的搜索和筛选功能
