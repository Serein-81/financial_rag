# 测试步骤：验证请求是否到达后端

## 步骤 1: 重新构建 Docker 容器（应用更改）

```bash
cd rag_backend
docker-compose up -d --build
```

等待 30 秒让容器完全启动。

## 步骤 2: 检查 /debug/ping 端点（验证后端运行）

```powershell
# 在 PowerShell 中运行
Invoke-RestMethod -Uri "http://127.0.0.1:8000/debug/ping" -Method GET
```

如果返回 `{"pong":true}`，说明后端正常运行。

## 步骤 3: 测试 /debug/test-upload 端点（验证文件上传请求）

```powershell
# 创建测试文件
$testFile = "$env:TEMP\test.pdf"
Set-Content -Path $testFile -Value "%PDF-1.4 test"

# 发送测试请求
Invoke-RestMethod -Uri "http://127.0.0.1:8000/debug/test-upload" `
    -Method POST `
    -Form @{ "file" = Get-Item $testFile } `
    -TimeoutSec 30
```

如果成功，返回：
```json
{
  "status": "ok",
  "filename": "test.pdf",
  "size": 14,
  "timestamp": 1234567890.123
}
```

## 步骤 4: 检查 Docker 日志

```bash
docker logs --tail 50 rag_backend
```

你应该看到类似这样的日志：
```
🔧 [TEST-UPLOAD] 收到请求! 文件: test.pdf, 大小: 14
```

## 步骤 5: 测试真实的 tax-reports 上传

现在用同样的方法测试 `/api/v1/tax-reports/upload`：

```powershell
# 需要先获取 Token
# 在浏览器 Console: localStorage.getItem('rag_token')
$token = "你的token"

$testFile = "$env:TEMP\test.pdf"
Set-Content -Path $testFile -Value "%PDF-1.4 test"

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT" `
    -Method POST `
    -Headers @{ "Authorization" = "Bearer $token" } `
    -Form @{ "file" = Get-Item $testFile } `
    -TimeoutSec 60
```

## 预期结果

### ✅ 如果 /debug/test-upload 成功：
- 问题可能在 tax-reports 端点的特定代码
- 检查 tax_report.py 中的上传处理逻辑

### ❌ 如果 /debug/test-upload 也失败：
- 问题在 Docker 容器或网络配置
- 检查 docker-compose.yml 的端口映射
- 检查容器日志

## 检查 Docker 日志命令

```bash
# 查看所有日志
docker logs rag_backend

# 实时查看日志
docker logs -f rag_backend

# 查找特定关键词
docker logs rag_backend 2>&1 | grep -i "test-upload\|tax-reports\|error"
```
