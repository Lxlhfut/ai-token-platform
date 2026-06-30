#!/bin/bash
# ==============================================================
# ai-token-platform ECS Deployment Script
# 目标: 阿里云 ECS (Ubuntu 20.04/22.04) + ylxunlapi.top
# 用法: chmod +x deploy.sh && sudo ./deploy.sh
# ==============================================================
set -e

# ---- 配置（部署前修改） ----
DOMAIN="ylxunlapi.top"
ADMIN_EMAIL="admin@example.com"              # Let's Encrypt 通知邮箱，改成你的
APP_SECRET_KEY=""                             # 64 位随机字符串，留空自动生成
ADMIN_PASSWORD=""                             # 管理后台密码，留空使用默认值

# ---- 颜色 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---- 检查 root ----
if [ "$EUID" -ne 0 ]; then
    err "请用 sudo 运行: sudo ./deploy.sh"
fi

log "=== ai-token-platform 部署开始 ==="
log "域名: ${DOMAIN}"

# ---- 1. 系统更新 ----
log "Step 1/7: 更新系统包..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y curl nginx certbot python3-certbot-nginx git ufw

# ---- 2. 安装 Docker ----
log "Step 2/7: 安装 Docker & Docker Compose..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
fi

if ! docker compose version &>/dev/null 2>&1; then
    apt-get install -y docker-compose-plugin
fi
log "Docker: $(docker --version), Compose: $(docker compose version)"

# ---- 3. 拉取项目 ----
log "Step 3/7: 部署项目代码..."
APP_DIR="/opt/ai-token-platform"
if [ -d "$APP_DIR" ]; then
    warn "项目目录已存在，跳过 git clone（如需更新请手动 git pull）"
else
    # 如果已通过 scp 上传，直接使用；否则从 git 克隆
    # git clone https://github.com/yourname/ai-token-platform.git $APP_DIR
    err "请先将项目上传到 /opt/ai-token-platform，命令: scp -r ./ root@ECS_IP:/opt/ai-token-platform"
fi

cd $APP_DIR

# ---- 4. 生成 .env ----
log "Step 4/7: 生成 .env 配置..."

if [ -z "$APP_SECRET_KEY" ]; then
    APP_SECRET_KEY=$(openssl rand -hex 32)
fi
if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="Admin123456!"
    warn "使用默认管理员密码，请登录后立即修改！"
fi

cat > .env <<EOF
SECRET_KEY=${APP_SECRET_KEY}
DATABASE_URL=sqlite+aiosqlite:///./data/platform.db
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
PLATFORM_NAME=AI Token Platform
CURRENCY=CNY
UPSTREAM_TIMEOUT=120
ALLOW_REGISTRATION=true
EOF
log ".env 已生成"

# ---- 5. 创建 data 目录 ----
mkdir -p data

# ---- 6. 启动 Docker 服务 ----
log "Step 5/7: 启动 Docker 服务..."
docker compose down 2>/dev/null || true
docker compose up -d --build

sleep 3
if docker compose ps | grep -q "Up"; then
    log "Docker 服务已启动"
else
    err "Docker 启动失败，请检查: docker compose logs"
fi

# ---- 7. 配置 Nginx + SSL ----
log "Step 6/7: 配置 Nginx 反向代理..."

cat > /etc/nginx/sites-available/api <<NGINX
# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name ${DOMAIN};

    # Let's Encrypt 验证
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS 主站
server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # certbot 会自动写入证书路径（先占位）
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # SSE / 长连接支持
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    proxy_buffering off;
    proxy_cache off;

    # Cursor / IDE 客户端可能传大 header
    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

# 先启用 HTTP-only（SSL 证书申请前）
ln -sf /etc/nginx/sites-available/api /etc/nginx/sites-enabled/api
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
log "Nginx 配置已生效（HTTP）"

# ---- 8. SSL 证书 ----
log "Step 7/7: 申请 SSL 证书..."

# Let's Encrypt 有频率限制，先 dry-run
if certbot certonly --dry-run --nginx -d ${DOMAIN} --non-interactive --agree-tos -m ${ADMIN_EMAIL} 2>&1; then
    log "Dry-run 通过，正式申请证书..."
    certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m ${ADMIN_EMAIL}
    log "SSL 证书已安装！"
else
    warn "Let's Encrypt 证书申请失败（可能 DNS 未生效或备案中）"
    warn "先使用 HTTP-only 配置:"
    cat > /etc/nginx/sites-available/api <<NGINX_HTTP
server {
    listen 80;
    server_name ${DOMAIN};

    proxy_read_timeout 300s;
    proxy_buffering off;
    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX_HTTP
    nginx -t && systemctl reload nginx
    warn "HTTP-only 模式已启用，备案完成后再运行: sudo certbot --nginx -d ${DOMAIN}"
fi

# ---- 防火墙 ----
log "配置防火墙..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
log "防火墙已开启: 22, 80, 443"

# ---- 完成 ----
echo ""
echo "============================================"
echo -e "  ${GREEN}DEPLOYMENT COMPLETE${NC}"
echo "============================================"
echo ""
echo "  域名:     https://${DOMAIN}"
echo "  管理后台: https://${DOMAIN}/admin"
echo "  API:      https://${DOMAIN}/v1/chat/completions"
echo ""
echo "  管理员账号: ${ADMIN_EMAIL}"
echo "  管理员密码: ${ADMIN_PASSWORD}"
echo ""
echo "  管理命令:"
echo "    docker compose logs -f       # 查看日志"
echo "    docker compose restart       # 重启服务"
echo "    docker compose down && docker compose up -d --build  # 重建"
echo ""
echo "  IMPORTANT:"
echo "  - 如果 SSL 失败：完成备案后运行 sudo certbot --nginx -d ${DOMAIN}"
echo "  - 如果域名无法访问：检查阿里云 DNS 是否已添加 A 记录指向本机公网 IP"
echo "============================================"
