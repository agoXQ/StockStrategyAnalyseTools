# 远程服务器部署指南

本文档介绍如何在远程服务器（Ubuntu系统）上部署选股策略跟踪工具。

## 1. 服务器环境准备

### 1.1 系统要求

- Ubuntu 20.04 或更高版本
- 至少 2GB RAM
- 至少 10GB 磁盘空间
- Python 3.8+
- Node.js 16+

### 1.2 安装系统依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础依赖
sudo apt install -y python3 python3-venv python3-full nodejs npm git curl wget

# 安装额外工具（可选）
sudo apt install -y htop vim net-tools
```

### 1.3 创建部署用户（推荐）

```bash
# 创建专用用户
sudo adduser stockapp
sudo usermod -aG sudo stockapp

# 切换到新用户
su - stockapp
```

## 2. 代码部署

### 2.1 克隆代码

```bash
# 克隆代码仓库
git clone <your-repo-url> StockStrategyAnalyseTools
cd StockStrategyAnalyseTools

# 或者使用scp上传代码
# 在本地执行：scp -r StockStrategyAnalyseTools user@server:/home/user/
```

### 2.2 设置权限

```bash
# 确保脚本可执行
chmod +x start.sh

# 设置正确的文件权限
chmod -R 755 .
```

## 3. 配置文件设置

### 3.1 配置环境变量

创建 `.env` 文件：

```bash
# 创建环境变量文件
cat > .env << EOF
# 数据库配置
DATABASE_URL=sqlite:///./stock_strategy.db

# 安全配置
SECRET_KEY=$(openssl rand -hex 32)
BOOTSTRAP_FIRST_USER_AS_ADMIN=true

# CORS配置（根据需要修改）
CORS_ALLOW_ORIGINS=http://your-domain.com,http://your-ip:19198

# 行情数据源配置
MARKET_DATA_PROVIDER=demo
TUSHARE_TOKEN=
JQDATA_USERNAME=
JQDATA_PASSWORD=
EOF

# 设置文件权限
chmod 600 .env
```

### 3.2 配置行情数据源

编辑 `config.yaml`：

```bash
vim config.yaml
```

根据需要修改行情数据源配置。

## 4. 依赖安装

### 4.1 安装后端依赖

```bash
# 使用脚本安装
./start.sh install

# 或手动安装
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4.2 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

## 5. 数据库配置

### 5.1 SQLite 配置（默认）

默认使用 SQLite，无需额外配置。

### 5.2 PostgreSQL 配置（可选）

```bash
# 安装PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 创建数据库
sudo -u postgres psql
CREATE DATABASE stock_strategy;
CREATE USER stockapp WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE stock_strategy TO stockapp;
\q

# 更新环境变量
export DATABASE_URL="postgresql://stockapp:your_password@localhost/stock_strategy"
```

## 6. 启动服务

### 6.1 测试启动

```bash
# 测试启动所有服务
./start.sh start

# 检查服务状态
./start.sh status

# 查看日志
./start.sh logs backend
./start.sh logs frontend
```

### 6.2 验证服务

```bash
# 检查端口
netstat -tlnp | grep -E '1145|19198'

# 测试API
curl http://localhost:1145/api/auth/me

# 测试前端
curl http://localhost:19198
```

## 7. 配置反向代理（可选但推荐）

### 7.1 安装Nginx

```bash
sudo apt install -y nginx
```

### 7.2 配置Nginx

创建配置文件 `/etc/nginx/sites-available/stock-strategy`：

```nginx
# 后端API代理
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        proxy_pass http://localhost:19198;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端API代理
    location /api {
        proxy_pass http://localhost:1145;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/stock-strategy /etc/nginx/sites-enabled/

# 删除默认配置
sudo rm /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
```

## 8. 配置SSL证书（推荐）

### 8.1 使用Let's Encrypt

```bash
# 安装Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

## 9. 配置防火墙

```bash
# 安装UFW
sudo apt install -y ufw

# 配置防火墙规则
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# 启用防火墙
sudo ufw enable

# 查看状态
sudo ufw status
```

## 10. 配置进程管理（推荐）

### 10.1 使用Systemd

创建后端服务文件 `/etc/systemd/system/stock-backend.service`：

```ini
[Unit]
Description=Stock Strategy Backend
After=network.target

[Service]
Type=simple
User=stockapp
WorkingDirectory=/home/stockapp/StockStrategyAnalyseTools
Environment="PATH=/home/stockapp/StockStrategyAnalyseTools/.venv/bin"
ExecStart=/home/stockapp/StockStrategyAnalyseTools/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 1145
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

创建前端服务文件 `/etc/systemd/system/stock-frontend.service`：

```ini
[Unit]
Description=Stock Strategy Frontend
After=network.target

[Service]
Type=simple
User=stockapp
WorkingDirectory=/home/stockapp/StockStrategyAnalyseTools/frontend
ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0 --port 19198
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
# 重新加载systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start stock-backend
sudo systemctl start stock-frontend

# 设置开机自启
sudo systemctl enable stock-backend
sudo systemctl enable stock-frontend

# 查看状态
sudo systemctl status stock-backend
sudo systemctl status stock-frontend

# 查看日志
sudo journalctl -u stock-backend -f
sudo journalctl -u stock-frontend -f
```

## 11. 监控和维护

### 11.1 日志管理

```bash
# 查看应用日志
./start.sh logs backend
./start.sh logs frontend

# 查看系统日志
sudo journalctl -xe

# 设置日志轮转
sudo vim /etc/logrotate.d/stock-strategy
```

创建日志轮转配置 `/etc/logrotate.d/stock-strategy`：

```
/home/stockapp/StockStrategyAnalyseTools/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 stockapp stockapp
}
```

### 11.2 备份

创建备份脚本 `backup.sh`：

```bash
#!/bin/bash

BACKUP_DIR="/home/stockapp/backups"
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR="/home/stockapp/StockStrategyAnalyseTools"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
cp $PROJECT_DIR/stock_strategy.db $BACKUP_DIR/stock_strategy_$DATE.db

# 备份配置文件
cp $PROJECT_DIR/config.yaml $BACKUP_DIR/config_$DATE.yaml
cp $PROJECT_DIR/.env $BACKUP_DIR/env_$DATE

# 压缩备份
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz $BACKUP_DIR/*_$DATE.*

# 清理旧备份（保留最近7天）
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +7 -delete

echo "备份完成: $BACKUP_DIR/backup_$DATE.tar.gz"
```

设置定时备份：

```bash
chmod +x backup.sh

# 添加到crontab（每天凌晨2点备份）
crontab -e
# 添加：0 2 * * * /home/stockapp/StockStrategyAnalyseTools/backup.sh
```

### 11.3 监控

```bash
# 检查磁盘空间
df -h

# 检查内存使用
free -h

# 检查进程
ps aux | grep -E 'uvicorn|npm'

# 检查端口
netstat -tlnp | grep -E '1145|19198'
```

## 12. 性能优化

### 12.1 生产环境配置

修改后端启动参数：

```bash
# 使用gunicorn（生产环境推荐）
pip install gunicorn

# 启动命令
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:1145
```

### 12.2 前端生产构建

```bash
cd frontend
npm run build

# 使用nginx提供静态文件服务
# 修改nginx配置指向dist目录
```

## 13. 故障排除

### 13.1 常见问题

**服务无法启动**

```bash
# 检查端口占用
sudo lsof -i :1145
sudo lsof -i :19198

# 检查日志
./start.sh logs backend
./start.sh logs frontend
```

**权限问题**

```bash
# 修复文件权限
chmod -R 755 /home/stockapp/StockStrategyAnalyseTools
chown -R stockapp:stockapp /home/stockapp/StockStrategyAnalyseTools
```

**数据库问题**

```bash
# 检查数据库文件
ls -la stock_strategy.db

# 修复数据库权限
chmod 644 stock_strategy.db
```

## 14. 安全建议

1. **定期更新系统**

   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **使用强密码**
   - 数据库密码
   - 管理员账户密码
   - JWT密钥

3. **限制SSH访问**

   ```bash
   # 禁用root登录
   sudo vim /etc/ssh/sshd_config
   # 修改：PermitRootLogin no

   # 重启SSH服务
   sudo systemctl restart sshd
   ```

4. **配置fail2ban**
   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   sudo systemctl start fail2ban
   ```

## 15. 快速部署脚本

创建一键部署脚本 `deploy.sh`：

```bash
#!/bin/bash

set -e

echo "开始部署选股策略跟踪工具..."

# 1. 安装系统依赖
echo "安装系统依赖..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-full nodejs npm git

# 2. 克隆代码
echo "部署代码..."
if [ ! -d "StockStrategyAnalyseTools" ]; then
    git clone <your-repo-url> StockStrategyAnalyseTools
fi
cd StockStrategyAnalyseTools

# 3. 设置权限
chmod +x start.sh

# 4. 配置环境变量
if [ ! -f ".env" ]; then
    cat > .env << EOF
DATABASE_URL=sqlite:///./stock_strategy.db
SECRET_KEY=$(openssl rand -hex 32)
BOOTSTRAP_FIRST_USER_AS_ADMIN=true
CORS_ALLOW_ORIGINS=http://$(hostname -I | awk '{print $1}'):19198
MARKET_DATA_PROVIDER=demo
EOF
    chmod 600 .env
fi

# 5. 安装依赖
echo "安装依赖..."
./start.sh install

# 6. 启动服务
echo "启动服务..."
./start.sh start

echo "部署完成！"
echo "前端地址: http://$(hostname -I | awk '{print $1}'):19198"
echo "API文档: http://$(hostname -I | awk '{print $1}'):1145/docs"
```

使用方法：

```bash
chmod +x deploy.sh
./deploy.sh
```

## 联系支持

如有问题，请查看：

- 项目README
- API文档：`http://your-server:1145/docs`
- 日志文件：`./start.sh logs backend`
