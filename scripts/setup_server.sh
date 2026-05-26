#!/bin/bash
# smart-stock 服务器一键部署脚本
# 适用: Ubuntu 22.04 / 24.04

set -e

echo "=== SmartStock 服务器部署 ==="

# 1. 系统依赖
echo "[1/5] 安装系统依赖..."
sudo apt update -qq
sudo apt install -y -qq python3 python3-pip python3-venv git

# 2. 拉取代码
echo "[2/5] 拉取项目代码..."
cd /opt
sudo git clone https://github.com/hirotei2023-hash/smart-stock.git 2>/dev/null || (cd smart-stock && sudo git pull)
sudo chown -R $USER:$USER /opt/smart-stock

# 3. 安装 Python 依赖
echo "[3/5] 安装 Python 依赖..."
cd /opt/smart-stock
pip3 install -r backend/requirements.txt --break-system-packages 2>/dev/null || pip3 install -r backend/requirements.txt

# 4. 创建 systemd 服务（开机自启）
echo "[4/5] 配置开机自启..."
sudo tee /etc/systemd/system/smart-stock.service > /dev/null << 'UNIT'
[Unit]
Description=SmartStock API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/smart-stock
ExecStart=/usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# 5. 启动服务
echo "[5/5] 启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable smart-stock
sudo systemctl restart smart-stock

echo ""
echo "=== 部署完成 ==="
echo "公网访问: http://$(curl -s ifconfig.me):8001"
echo "查看状态: sudo systemctl status smart-stock"
echo "查看日志: sudo journalctl -u smart-stock -f"
