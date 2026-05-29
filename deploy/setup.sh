#!/bin/bash
# ============================================
# 邹卫华律师团队网站 - 服务器一键部署脚本
# 适用: Ubuntu 20.04+ / 22.04+
# ============================================
set -e

echo "========================================"
echo "   邹卫华律师团队网站 - 部署脚本"
echo "========================================"

# ---- 1. 更新系统 ----
echo "[1/6] 更新系统..."
apt-get update -y

# ---- 2. 安装依赖 ----
echo "[2/6] 安装 Python 和 Nginx..."
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# ---- 3. 创建项目目录 ----
echo "[3/6] 设置项目目录..."
mkdir -p /var/www/ynlawyers
cp -r ./* /var/www/ynlawyers/
chown -R www-data:www-data /var/www/ynlawyers

# ---- 4. 安装 Python 依赖 ----
echo "[4/6] 安装 Python 依赖..."
cd /var/www/ynlawyers
pip3 install --break-system-packages -r requirements.txt

# ---- 5. 配置 Nginx ----
echo "[5/6] 配置 Nginx..."
cp deploy/ynlawyers-nginx.conf /etc/nginx/sites-available/ynlawyers.com
ln -sf /etc/nginx/sites-available/ynlawyers.com /etc/nginx/sites-enabled/
# 删除默认站点
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ---- 6. 配置 systemd 服务 ----
echo "[6/6] 配置自动启动..."
cp deploy/ynlawyers.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ynlawyers
systemctl start ynlawyers

# ---- 7. SSL 证书 ----
echo ""
echo "========================================"
echo "   部署完成！"
echo "========================================"
echo ""
echo "下一步 - 配置 SSL 证书:"
echo "  certbot --nginx -d ynlawyers.com -d www.ynlawyers.com"
echo ""
echo "访问地址:"
echo "  http://ynlawyers.com"
echo "  http://43.135.112.189"
echo ""
echo "后台管理:"
echo "  http://ynlawyers.com/admin"
echo "  账号: admin / admin123"
echo ""
echo "检查服务状态:"
echo "  systemctl status ynlawyers"
echo "  systemctl status nginx"
echo ""
