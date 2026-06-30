# 域名绑定部署指南

## 概览

将 `ylxunlapi.top` 绑定到阿里云 ECS（120.26.162.115），实现 HTTPS 访问。

## 前置条件

- [ ] 阿里云 ECS 已运行 Docker + 项目（`docker ps` 能看到容器）
- [ ] 已备案域名 `ylxunlapi.top`（已满足）
- [ ] 阿里云安全组放行 **80** 和 **443** 端口

---

## 步骤一：阿里云 DNS 解析

登录 [阿里云控制台 → 云解析 DNS](https://dns.console.aliyun.com/)

添加以下 2 条 A 记录：

| 记录类型 | 主机记录 | 记录值           |
|---------|---------|-----------------|
| A       | `@`     | 120.26.162.115  |
| A       | `www`   | 120.26.162.115  |

> TTL 设为 10 分钟，等待 5-10 分钟生效后继续。

---

## 步骤二：检查安全组端口

阿里云控制台 → ECS → 安全组 → 入方向规则，确认有：

| 协议 | 端口 | 来源      |
|-----|------|----------|
| TCP | 80   | 0.0.0.0/0 |
| TCP | 443  | 0.0.0.0/0 |

---

## 步骤三：上传并执行部署脚本

### 3.1 上传文件到服务器

```bash
# 在本地执行（将 deploy 目录上传到服务器）
scp -r deploy/ root@120.26.162.115:/root/deploy/
```

### 3.2 修改邮箱（用于证书过期提醒）

```bash
# 登录服务器后执行
ssh root@120.26.162.115
nano /root/deploy/setup.sh
# 修改第 9 行 EMAIL="admin@ylxunlapi.top" 为你的真实邮箱
```

### 3.3 执行一键脚本

```bash
ssh root@120.26.162.115

# 赋予执行权限
chmod +x /root/deploy/setup.sh

# 执行（约 1-2 分钟）
sudo bash /root/deploy/setup.sh
```

---

## 步骤四：验证

脚本执行成功后访问：

- **HTTPS 主域名**: https://ylxunlapi.top
- **www 子域名**: https://www.ylxunlapi.top

浏览器地址栏应显示 🔒 锁图标，证明 HTTPS 配置成功。

---

## 常见问题

### 证书申请失败

原因：DNS 未生效或 80 端口未放行。

```bash
# 检查 DNS 是否解析正确
dig ylxunlapi.top

# 手动申请证书（重新执行）
certbot --nginx -d ylxunlapi.top -d www.ylxunlapi.top --email 你的邮箱 --agree-tos --non-interactive
```

### Nginx 配置测试失败

```bash
nginx -t          # 检查配置语法
systemctl status nginx  # 查看 Nginx 状态
journalctl -xe    # 查看详细错误日志
```

### 网站无法访问（Docker 容器问题）

```bash
docker ps                         # 检查容器是否运行
docker-compose -f /path/to/docker-compose.yml up -d  # 启动容器
curl http://127.0.0.1:8000        # 测试本地接口
```

### 证书续期

证书有效期 90 天，已通过 cron 配置自动续期。手动续期：

```bash
certbot renew --dry-run   # 模拟续期（测试）
certbot renew             # 实际续期
systemctl reload nginx
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `nginx.conf` | Nginx 完整配置（含 HTTPS、反代、流式输出支持） |
| `setup.sh` | 一键安装脚本（Nginx + Certbot + 配置部署） |
| `README.md` | 本文档 |
