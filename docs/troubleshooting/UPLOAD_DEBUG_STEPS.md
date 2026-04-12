# 上传接口调试指南

## 问题描述
前端显示上传超时，后端没有任何日志，说明请求没有到达后端。

## 🔍 诊断步骤

### 步骤 1：确认后端是否运行

在浏览器中访问：
```
http://127.0.0.1:8000/health
```

应该返回 `{"status":"ok"}` 或类似内容。

如果无法访问，说明后端没有启动。

### 步骤 2：使用 curl 测试

从浏览器控制台获取 token：
```javascript
copy(localStorage.getItem('rag_token'))
```

然后在终端执行：
```bash
# 创建测试文件
echo "%PDF-1.4 test" > test.pdf

# 测试上传（将 YOUR_TOKEN 替换为实际的 token）
curl -X POST "http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf" \
  -v

# 清理
rm test.pdf
```

### 步骤 3：检查浏览器网络请求

1. 打开开发者工具 (F12)
2. 切换到 Network 标签
3. 勾选 "Preserve log"（保留日志）
4. 上传文件
5. 查看请求详情：
   - **Status**: 是什么状态码？
   - **Timing**: 耗时多久？
   - **Response**: 返回了什么？

### 步骤 4：查看后端日志

重启后端后，应该看到类似日志：

```
🏠 [8cbd5945] POST /api/v1/tax-reports/upload
📤 [TaxUpload] 收到上传请求: xxx.pdf, 大小: xxx
⏱️ [TaxUpload] Step 1: 开始读取文件内容... 0.01s
...
🚀 [TaxUpload] 快速返回: 报告ID=xxx, 总耗时: 0.15s
```

如果看不到这些日志，说明请求没有到达后端。

## 常见问题及解决方案

### ❌ 情况 1：后端没有启动

**现象**：无法访问 `http://127.0.0.1:8000/health`

**解决**：
```bash
cd rag_backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### ❌ 情况 2：后端已启动但请求未到达

**现象**：后端在运行，但上传请求没有日志

**解决**：
1. 确认前端请求的端口与后端监听端口一致
2. 检查 `rag_frontend/src/api/tax-report.ts` 中的 `API_BASE`
3. 检查浏览器网络请求，看是否有 CORS 错误

### ❌ 情况 3：Token 无效

**现象**：后端日志显示 `❌ [AUTH] Token invalid`

**解决**：
1. 清除浏览器 localStorage 中的 `rag_token`
2. 重新登录获取新 token
3. 刷新页面

### ❌ 情况 4：限流拦截

**现象**：后端日志显示 `⏳ [RATE] /api/v1/tax-reports/upload - Limited`

**解决**：等待 60 秒后再试

### ❌ 情况 5：路由错误

**现象**：请求到达后端但返回 404

**检查**：确认路由配置正确
- 前端请求: `/api/v1/tax-reports/upload`
- 后端路由: `prefix="/api/v1/tax-reports"` + `@router.post("/upload")`

## 🎯 关键日志标记

| 标记 | 含义 |
|------|------|
| `🏠 [USER_ID]` | 租户中间件处理（USER_ID 是用户ID前8位） |
| `📤 [TaxUpload]` | 上传端点处理 |
| `⏱️` | 性能计时 |
| `🚀` | 上传成功返回 |
| `❌ [AUTH]` | 认证错误 |
| `⏳ [RATE]` | 限流拦截 |
| `🔍` | 慢请求或错误响应 |

## 📝 修改的文件

1. `rag_backend/app/middleware/logging_middleware.py` - 简化日志
2. `rag_backend/app/middleware/tenant_middleware.py` - 简化日志
3. `rag_backend/app/middleware/rate_limit_middleware.py` - 简化日志
4. `rag_backend/app/api/v1/endpoints/tax_report.py` - 添加性能日志
5. `rag_frontend/src/api/tax-report.ts` - 添加调试日志

## ✅ 验证修复

修复后，应该看到完整的日志序列：

```
🏠 [8cbd5945] POST /api/v1/tax-reports/upload
📤 [TaxUpload] 收到上传请求: xxx.pdf, 大小: xxx
📤 [TaxUpload] 准备发送请求...
📤 [TaxUpload] 设置 Authorization header
📤 [TaxUpload] 发送表单数据
📤 [TaxUpload] send() 已调用，等待响应...
📤 [TaxUpload] 上传进度: 50%
📤 [TaxUpload] 上传进度: 100%
📤 [TaxUpload] 请求完成: 201 Created
📤 [TaxUpload] 上传成功: {...}
🚀 [TaxUpload] 快速返回: 报告ID=xxx, 总耗时: 0.15s
```

## 🚀 性能基准

- **文件读取**: < 0.1s
- **文件保存**: < 0.5s
- **数据库提交**: < 1s
- **总耗时**: < 2s

如果任何步骤超过以上时间，说明存在问题。
