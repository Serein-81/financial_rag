#!/bin/bash

# HTTPS 配置测试脚本

echo "================================"
echo "  HTTPS 配置测试"
echo "================================"
echo ""

# 测试 1: 检查 HTTPS 连接
echo "1️⃣  测试 HTTPS 连接..."
response=$(curl -k -s -o /dev/null -w "%{http_code}" https://localhost)
if [ "$response" = "200" ]; then
    echo "   ✅ HTTPS 连接正常 (HTTP $response)"
else
    echo "   ❌ HTTPS 连接失败 (HTTP $response)"
fi

# 测试 2: 检查证书
echo ""
echo "2️⃣  检查 SSL 证书..."
if [ -f "ssl/localhost.crt" ]; then
    echo "   ✅ 证书文件存在"

    # 检查证书信息
    expiry=$(openssl x509 -noout -enddate -in ssl/localhost.crt 2>/dev/null | cut -d= -f2)
    if [ -n "$expiry" ]; then
        echo "   📅 证书过期时间: $expiry"
    fi
else
    echo "   ❌ 证书文件不存在"
fi

# 测试 3: 检查 HTTP 重定向
echo ""
echo "3️⃣  测试 HTTP → HTTPS 重定向..."
redirect_response=$(curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}" http://localhost)
if [[ $redirect_response == "301"* ]]; then
    echo "   ✅ HTTP 重定向正常: $redirect_response"
else
    echo "   ⚠️  HTTP 重定向响应: $redirect_response"
fi

# 测试 4: 检查安全头
echo ""
echo "4️⃣  检查安全响应头..."
headers=$(curl -k -s -I https://localhost 2>/dev/null | grep -i "strict-transport\|x-frame\|x-content")

if [ -n "$headers" ]; then
    echo "   ✅ 安全头已配置:"
    echo "$headers" | sed 's/^/      /'
else
    echo "   ⚠️  未检测到安全响应头"
fi

# 测试 5: 检查容器状态
echo ""
echo "5️⃣  检查 Docker 容器..."
if docker ps | grep -q rag-frontend-https; then
    echo "   ✅ 容器正在运行"
    port_80=$(docker port rag-frontend-https 80 2>/dev/null | cut -d' ' -f3)
    port_443=$(docker port rag-frontend-https 443 2>/dev/null | cut -d' ' -f3)
    echo "   📦 端口映射:"
    echo "      HTTP:  $port_80"
    echo "      HTTPS: $port_443"
else
    echo "   ❌ 容器未运行"
fi

# 测试 6: OpenSSL 连接测试
echo ""
echo "6️⃣  OpenSSL 连接测试..."
if echo | openssl s_client -connect localhost:443 2>/dev/null | grep -q "SSL handshake has read"; then
    echo "   ✅ SSL/TLS 握手成功"
else
    echo "   ⚠️  无法完成 SSL 握手"
fi

echo ""
echo "================================"
echo "  测试完成"
echo "================================"
echo ""
echo "📝 后续步骤:"
echo "   1. 在浏览器中访问 https://localhost"
echo "   2. 接受自签名证书警告"
echo "   3. 验证页面正常加载"
echo "   4. 检查浏览器开发者工具 -> Network -> 查看请求协议"
echo ""
