#!/bin/bash

# RAG Frontend HTTPS 启动脚本
# 用于本地测试 HTTPS 功能

set -e

echo "================================"
echo "  RAG Frontend - HTTPS 模式"
echo "================================"
echo ""

# 检查 SSL 证书
if [ ! -f "ssl/localhost.crt" ] || [ ! -f "ssl/localhost.key" ]; then
    echo "⚠️  SSL 证书不存在，正在生成..."
    mkdir -p ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/localhost.key \
        -out ssl/localhost.crt \
        -subj "/C=CN/ST=Beijing/L=Beijing/O=MyRag/CN=localhost" \
        -config ssl/openssl.cnf 2>/dev/null || {
        echo "❌ OpenSSL 不可用，请先安装 OpenSSL"
        exit 1
    }
    echo "✅ SSL 证书生成完成"
else
    echo "✅ SSL 证书已存在"
fi

echo ""
echo "🔨 构建 Docker 镜像..."

# 构建镜像
docker build -t rag-frontend:https .

echo ""
echo "🚀 启动 HTTPS 服务..."

# 停止旧容器（如果存在）
docker stop rag-frontend-https 2>/dev/null || true
docker rm rag-frontend-https 2>/dev/null || true

# 启动新容器
docker run -d \
    --name rag-frontend-https \
    -p 80:80 \
    -p 443:443 \
    rag-frontend:https

echo ""
echo "================================"
echo "  ✅ 服务启动成功！"
echo "================================"
echo ""
echo "📍 访问地址："
echo "   • HTTPS: https://localhost"
echo "   • HTTP:  http://localhost (自动重定向)"
echo ""
echo "⚠️  首次访问 HTTPS 时，"
echo "   浏览器会显示安全警告（自签名证书）"
echo "   请点击'高级' → '继续前往 localhost'"
echo ""
echo "📝 常用命令："
echo "   • 查看日志: docker logs -f rag-frontend-https"
echo "   • 停止服务: docker stop rag-frontend-https"
echo "   • 删除容器: docker rm rag-frontend-https"
echo ""
echo "📚 详细文档: cat HTTPS_DEPLOYMENT.md"
echo ""
