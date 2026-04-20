# HTTPS 部署指南

本指南详细说明如何为 RAG 前端配置 HTTPS/SSL。

## 📋 目录

- [快速开始](#快速开始)
- [SSL 证书说明](#ssl-证书说明)
- [Docker 部署](#docker-部署)
- [生产环境配置](#生产环境配置)
- [测试与验证](#测试与验证)
- [故障排除](#故障排除)

## 🚀 快速开始

### 1. 启动 HTTPS 服务

```bash
cd rag_frontend

# 构建 Docker 镜像
docker build -t rag-frontend:https .

# 运行容器（同时暴露 HTTP 和 HTTPS）
docker run -d \
  --name rag-frontend-https \
  -p 80:80 \
  -p 443:443 \
  rag-frontend:https
```

### 2. 访问服务

- **HTTP**: http://localhost (会自动重定向到 HTTPS)
- **HTTPS**: https://localhost (使用自签名证书)

> ⚠️ **重要**: 首次访问 https://localhost 时，浏览器会显示安全警告，因为使用的是自签名证书。这是正常的，点击"高级" → "继续前往 localhost"即可。

## 🔐 SSL 证书说明

### 当前配置

项目使用 **自签名证书**，适用于：
- ✅ 本地开发/测试
- ✅ 学习 HTTPS 工作原理
- ✅ CI/CD 测试环境

**不适用于**：
- ❌ 公网生产环境
- ❌ 需要受浏览器信任的站点

### 证书文件

```
rag_frontend/ssl/
├── localhost.crt      # SSL 证书（公钥）
├── localhost.key     # SSL 私钥
└── openssl.cnf       # OpenSSL 配置文件
```

### 生成新证书

如果需要为不同域名生成证书：

```bash
cd rag_frontend/ssl

# 为特定域名生成证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout yourdomain.key \
  -out yourdomain.crt \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=YourOrg/CN=yourdomain.com" \
  -config openssl.cnf
```

## 🐳 Docker 部署

### 独立部署前端

```yaml
# frontend-https.yml
version: '3.8'

services:
  frontend:
    build:
      context: ./rag_frontend
      dockerfile: Dockerfile
    container_name: rag_frontend_https
    ports:
      - "80:80"
      - "443:443"
    restart: unless-stopped
    volumes:
      # 可选：挂载自定义证书
      - ./rag_frontend/ssl:/etc/nginx/ssl:ro
```

启动命令：
```bash
docker-compose -f frontend-https.yml up -d
```

### 完整系统部署（包含后端）

```yaml
# docker-compose.https.yml
version: '3.8'

services:
  frontend:
    build:
      context: ./rag_frontend
      dockerfile: Dockerfile
    container_name: rag_frontend_https
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    restart: unless-stopped

  backend:
    build:
      context: ./rag_backend
      dockerfile: Dockerfile
    container_name: rag_backend
    ports:
      - "8000:8000"
    environment:
      # ... 其他环境变量
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # ... 其他服务（db, redis, neo4j, minio, pgbouncer）
```

## 🏭 生产环境配置

### 方案 1: Let's Encrypt（推荐）

适用于有真实域名的生产环境，自动续期，完全免费。

#### 1. 安装 Certbot

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install certbot python3-certbot-nginx
```

#### 2. 获取证书

```bash
# 为你的域名获取证书
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 自动续期测试
sudo certbot renew --dry-run
```

#### 3. Nginx 配置（Certbot 自动生成）

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # ACME 挑战验证
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # Certbot 自动配置这些
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # ... 其他配置
}
```

### 方案 2: 商业证书

如果你有商业 SSL 证书（如 DigiCert, Comodo 等）：

1. **上传证书文件到服务器**
   ```bash
   # 创建证书目录
   sudo mkdir -p /etc/nginx/ssl

   # 上传证书
   sudo scp your_cert.crt user@server:/tmp/
   sudo scp your_private_key.key user@server:/tmp/

   # 移动到正确位置
   sudo mv /tmp/your_cert.crt /etc/nginx/ssl/server.crt
   sudo mv /tmp/your_private_key.key /etc/nginx/ssl/server.key
   sudo chmod 600 /etc/nginx/ssl/server.key
   ```

2. **配置 Nginx**
   ```nginx
   ssl_certificate /etc/nginx/ssl/server.crt;
   ssl_certificate_key /etc/nginx/ssl/server.key;
   ```

### 方案 3: Docker + Nginx Proxy Companion

适用于 Docker Compose 部署的自动 HTTPS：

```yaml
version: '3.8'

services:
  nginx-proxy:
    image: nginxproxy/nginx-proxy:latest
    container_name: nginx-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/tmp/docker.sock:ro
      - ./nginx/vhost.d:/etc/nginx/vhost.d
      - ./nginx/html:/usr/share/nginx/html
      - ./nginx/acme:/etc/acme.sh

  acme-companion:
    image: nginxproxy/acme-companion:latest
    container_name: acme-companion
    environment:
      - DEFAULT_EMAIL=your-email@example.com
    volumes_from:
      - nginx-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./nginx/acme:/etc/acme.sh

  frontend:
    # ... 其他配置
    environment:
      - VIRTUAL_HOST=yourdomain.com
      - VIRTUAL_PORT=80
      - LETSENCRYPT_HOST=yourdomain.com
      - LETSENCRYPT_EMAIL=your-email@example.com
```

## 🧪 测试与验证

### 1. 测试 HTTPS 连接

```bash
# 使用 curl 测试（忽略证书验证）
curl -k https://localhost

# 使用 OpenSSL 测试连接
openssl s_client -connect localhost:443 -showcerts

# 详细测试
openssl s_client -connect localhost:443 -debug
```

### 2. 检查 SSL 配置

使用在线工具：
- [SSL Labs](https://www.ssllabs.com/ssltest/) - 在线 SSL 测试
- [ImmuniWeb](https://www.immuniweb.com/ssl/) - SSL 安全评估

本地检查：
```bash
# 检查证书信息
openssl x509 -in ssl/localhost.crt -text -noout

# 验证证书和私钥匹配
openssl x509 -noout -modulus -in ssl/localhost.crt | md5sum
openssl rsa -noout -modulus -in ssl/localhost.key | md5sum
# 两个 MD5 值应该相同

# 检查证书过期时间
openssl x509 -noout -enddate -in ssl/localhost.crt
```

### 3. 检查安全头部

```bash
# 查看响应头
curl -I https://localhost

# 应该看到以下安全头：
# Strict-Transport-Security: max-age=31536000; includeSubDomains
# X-Content-Type-Options: nosniff
# X-Frame-Options: SAMEORIGIN
# X-XSS-Protection: 1; mode=block
```

### 4. 验证重定向

```bash
# 测试 HTTP → HTTPS 重定向
curl -I http://localhost
# 应该返回 301 重定向到 https://localhost
```

## 🔧 故障排除

### 问题 1: 浏览器显示"连接不安全"

**原因**: 使用自签名证书，浏览器不信任

**解决方案**:
1. 点击"高级"
2. 点击"继续前往 localhost（不安全）"
3. 或者安装自签名证书到系统信任存储

**永久信任（仅测试环境）**:
- **Windows**: 
  ```powershell
  # 以管理员身份运行 PowerShell
  Import-Certificate -FilePath "ssl/localhost.crt" -CertStoreLocation Cert:\LocalMachine\Root
  ```
- **macOS**: 
  ```bash
  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ssl/localhost.crt
  ```

### 问题 2: 证书文件找不到

**检查**:
```bash
# 在容器内检查
docker exec -it rag_frontend_https ls -la /etc/nginx/ssl/

# 应该看到：
# -rw-r--r-- 1 root root 1391 localhost.crt
# -rw------- 1 root root 1704 localhost.key
```

**解决**: 确保 Dockerfile 中正确复制了证书文件

### 问题 3: 端口 443 被占用

```bash
# Windows: 查看端口占用
netstat -ano | findstr :443

# 停止占用进程或修改配置使用其他端口
```

### 问题 4: HTTPS 工作但 HTTP 不重定向

**检查 Nginx 配置**:
```bash
# 查看错误日志
docker logs rag_frontend_https 2>&1 | grep error

# 测试配置
docker exec rag_frontend_https nginx -t
```

## 📚 工作原理

### SSL Termination 流程

```
用户浏览器                    Nginx (Frontend)                    FastAPI (Backend)
    |                              |                                     |
    |  1. HTTPS://localhost        |                                     |
    |  (加密连接 TLS 1.3)          |                                     |
    |----------------------------->|                                     |
    |                              |                                     |
    |  2. Nginx 解密请求            |                                     |
    |     (SSL Termination)       |                                     |
    |                              |                                     |
    |  3. 转发到 http://backend    |                                     |
    |     (明文 HTTP)              |                                     |
    |                              |------------------------------------>|
    |                              |                                     |
    |  4. 返回响应                 |                                     |
    |     (明文 HTTP)              |                                     |
    |<------------------------------|                                     |
    |                              |                                     |
    |  5. Nginx 加密响应           |                                     |
    |     (SSL Encryption)         |                                     |
    |                              |                                     |
```

### 为什么使用 SSL Termination？

| 优势 | 说明 |
|------|------|
| **减轻 CPU 负担** | Nginx 专门处理加解密，性能优于 Python 应用 |
| **统一证书管理** | 只需在一个地方配置证书 |
| **内网高速传输** | 后端通信使用明文，零加密开销 |
| **便于扩展** | 可以轻松添加负载均衡、CDN 等 |
| **更好的安全** | 证书不在应用服务器，降低泄露风险 |

## 📝 配置清单

### 开发环境 ✅
- [x] 自签名证书
- [x] HTTP → HTTPS 重定向
- [x] 安全响应头
- [x] Gzip 压缩
- [x] 静态资源缓存

### 生产环境（待完成）
- [ ] Let's Encrypt 或商业证书
- [ ] 域名 DNS 配置
- [ ] 防火墙规则（80, 443）
- [ ] 自动续期机制
- [ ] 性能监控
- [ ] 日志集中管理

## 🎯 下一步

1. **测试当前配置**: 启动服务并验证 HTTPS 功能
2. **学习 SSL/TLS**: 阅读相关协议知识
3. **准备生产环境**: 获取真实域名和证书
4. **监控与维护**: 设置证书过期提醒

## 📞 支持

遇到问题？
1. 检查 [故障排除](#故障排除) 章节
2. 查看 Nginx 错误日志
3. 提交 Issue 到项目仓库

---

**祝你在学习 HTTPS 的过程中收获满满！** 🚀
