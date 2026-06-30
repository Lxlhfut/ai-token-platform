#!/bin/bash
# =============================================================
# ai-token-platform 域名绑定一键部署脚本
# 适用于: 阿里云 ECS (Alibaba Cloud Linux 3 / CentOS 8+)
# 域名: ylxunlapi.top
# 服务器 IP: 120.26.162.115
# =============================================================

set -e  # 任何命令失败立即退出

DOMAIN="ylxunlapi.top"
EMAIL="admin@ylxunlapi.top"   # ← 改成你的真实邮箱（用于 Let's Encrypt 过期提醒）
APP_DIR="/opt/ai-token-platform"

echo "========================================"
echo " 开始配置域名绑定: $DOMAIN"
echo "========================================"

# --------------------------------------------------
# 1. 安装 Nginx
# --------------------------------------------------
echo "[1/5] 安装 Nginx..."
if command -v dnf &>/dev/null; then
    dnf install -y nginx
elif command -v yum &>/dev/null; then
    yum install -y nginx
elif command -v apt-get &>/dev/null; then
    apt-get update && apt-get install -y nginx
fi

systemctl enable nginx
systemctl start nginx
echo "    Nginx 已安装并启动"

# --------------------------------------------------
# 2. 安装 Certbot（Let's Encrypt SSL 证书工具）
# --------------------------------------------------
echo "[2/5] 安装 Certbot..."
if command -v dnf &>/dev/null; then
    dnf install -y python3-certbot-nginx || (
        dnf install -y epel-release && dnf install -y certbot python3-certbot-nginx
    )
elif command -v apt-get &>/dev/null; then
    apt-get install -y certbot python3-certbot-nginx
fi
echo "    Certbot 已安装"

# --------------------------------------------------
# 3. 部署 Nginx 配置（HTTP 临时配置，用于 Certbot 验证）
# --------------------------------------------------
echo "[3/5] 部署 Nginx 配置..."

# 创建 Certbot webroot 目录
mkdir -p /var/www/certbot

# 检测 Nginx 配置目录类型（Ubuntu: sites-available，CentOS: conf.d）
if [ -d /etc/nginx/sites-available ]; then
    NGINX_AVAILABLE="/etc/nginx/sites-available"
    NGINX_ENABLED="/etc/nginx/sites-enabled"
elif [ -d /etc/nginx/conf.d ]; then
    NGINX_AVAILABLE="/etc/nginx/conf.d"
    NGINX_ENABLED=""
else
    echo "错误: 找不到 Nginx 配置目录！"
    exit 1
fi

# 先写一个只有 HTTP 的临时配置（Certbot 验证需要）
CONF_FILE="$NGINX_AVAILABLE/$DOMAIN"
if [ -z "$NGINX_ENABLED" ]; then
    CONF_FILE="$CONF_FILE.conf"
fi

cat > "$CONF_FILE" << 'NGINX_HTTP'
server {
    listen 80;
    listen [::]:80;
    server_name ylxunlapi.top www.ylxunlapi.top;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_HTTP

# Ubuntu 需要 sites-enabled 软链接
if [ -n "$NGINX_ENABLED" ]; then
    ln -sf "$CONF_FILE" "$NGINX_ENABLED/$DOMAIN"
fi

nginx -t && systemctl reload nginx
echo "    Nginx HTTP 配置已生效"

# --------------------------------------------------
# 4. 申请 SSL 证书
# --------------------------------------------------
echo "[4/5] 申请 Let's Encrypt SSL 证书..."
echo "    域名: $DOMAIN, www.$DOMAIN"
echo "    邮箱: $EMAIL"

certbot --nginx \
    -d $DOMAIN \
    -d www.$DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --non-interactive \
    --redirect

echo "    SSL 证书申请成功！"

# --------------------------------------------------
# 5. 替换为完整的 HTTPS 配置
# --------------------------------------------------
echo "[5/5] 更新 Nginx HTTPS 配置..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/nginx.conf" ]; then
    cp "$SCRIPT_DIR/nginx.conf" "$CONF_FILE"
    if [ -n "$NGINX_ENABLED" ]; then
        ln -sf "$CONF_FILE" "$NGINX_ENABLED/$DOMAIN"
    fi
    nginx -t && systemctl reload nginx
    echo "    完整 HTTPS 配置已部署"
fi

# --------------------------------------------------
# 设置证书自动续期
# --------------------------------------------------
echo "[+] 配置证书自动续期..."
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
echo "    自动续期已配置（每天凌晨 3 点检查）"

# --------------------------------------------------
# 验证
# --------------------------------------------------
echo ""
echo "========================================"
echo " 部署完成！"
echo "========================================"
echo " 访问地址: https://$DOMAIN"
echo " 证书路径: /etc/letsencrypt/live/$DOMAIN/"
echo ""
echo " 如果访问失败，请检查："
echo "  1. 阿里云安全组是否放行 80 和 443 端口"
echo "  2. DNS 是否已解析到 120.26.162.115"
echo "  3. Docker 容器是否正在运行: docker ps"
echo "========================================"
