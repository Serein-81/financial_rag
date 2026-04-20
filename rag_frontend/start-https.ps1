# RAG Frontend HTTPS 启动脚本 (PowerShell)
# 用于本地测试 HTTPS 功能

param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  RAG Frontend - HTTPS 模式" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# 检查 SSL 证书
$certPath = "ssl\localhost.crt"
$keyPath = "ssl\localhost.key"

if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
    Write-Host "SSL 证书不存在，正在生成..." -ForegroundColor Yellow

    if (-not (Test-Path "ssl")) {
        New-Item -ItemType Directory -Path "ssl" -Force | Out-Null
    }

    # 检查 OpenSSL
    try {
        $null = Get-Command openssl -ErrorAction Stop
    } catch {
        Write-Host "错误: OpenSSL 未安装" -ForegroundColor Red
        Write-Host "请先安装 OpenSSL: https://slproweb.com/products/Win32OpenSSL.html" -ForegroundColor Yellow
        exit 1
    }

    # 生成证书
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout $keyPath `
        -out $certPath `
        -subj "/C=CN/ST=Beijing/L=Beijing/O=MyRag/CN=localhost" `
        -config ssl\openssl.cnf

    Write-Host "SSL 证书生成完成" -ForegroundColor Green
} else {
    Write-Host "SSL 证书已存在" -ForegroundColor Green
}

Write-Host ""
Write-Host "构建 Docker 镜像..." -ForegroundColor Cyan

# 构建镜像
docker build -t rag-frontend:https .

Write-Host ""
Write-Host "启动 HTTPS 服务..." -ForegroundColor Cyan

# 停止旧容器
docker stop rag-frontend-https 2>$null
docker rm rag-frontend-https 2>$null

# 启动新容器
docker run -d `
    --name rag-frontend-https `
    -p 80:80 `
    -p 443:443 `
    rag-frontend:https

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "  服务启动成功！" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "访问地址：" -ForegroundColor Cyan
Write-Host "   HTTPS: https://localhost" -ForegroundColor White
Write-Host "   HTTP:  http://localhost (自动重定向)" -ForegroundColor White
Write-Host ""
Write-Host "注意: 首次访问 HTTPS 时，浏览器会显示安全警告（自签名证书）" -ForegroundColor Yellow
Write-Host "      请点击'高级' -> '继续前往 localhost'" -ForegroundColor Yellow
Write-Host ""
Write-Host "常用命令：" -ForegroundColor Cyan
Write-Host "   查看日志: docker logs -f rag-frontend-https" -ForegroundColor White
Write-Host "   停止服务: docker stop rag-frontend-https" -ForegroundColor White
Write-Host "   删除容器: docker rm rag-frontend-https" -ForegroundColor White
Write-Host ""
Write-Host "详细文档: cat HTTPS_DEPLOYMENT.md" -ForegroundColor Cyan
Write-Host ""
