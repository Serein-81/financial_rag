# 上传问题诊断指南

## 🎯 问题描述
上传文件后，后端没有任何日志输出，说明请求没有到达后端。

## 🔍 诊断步骤

### 第一步：检查后端是否运行

在后端终端中，应该看到类似这样的日志：

```
🌐 [HTTP] POST /api/v1/tax-reports/upload - Request ID: xxx-xxx-xxx
```

**如果看不到这个日志**，说明请求没有到达后端。检查：

1. 后端服务是否正在运行？
   ```bash
   cd rag_backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. 端口是否正确？前端请求的是哪个端口？
   - 检查 `rag_frontend/src/api/tax-report.ts` 中的 `API_BASE`
   - 检查后端是否监听在相同的端口

### 第二步：检查中间件日志

重启后端后，上传文件应该看到以下日志序列：

```
🌐 [HTTP] POST /api/v1/tax-reports/upload - Request ID: xxx-xxx-xxx
🏠 [Tenant] Processing: POST /api/v1/tax-reports/upload
✅ [Tenant] Context set: tenant=xxx, user=xxx
⚡ [RateLimit] Allowed: POST /api/v1/tax-reports/upload (key=user:xxx)
📤 [TaxUpload] 收到上传请求: xxx.pdf, 大小: xxx
⏱️ [TaxUpload] Step 1: 开始读取文件内容...
...
🚀 [TaxUpload] 快速返回: 报告ID=xxx, 总耗时: 0.15s
✅ [HTTP] POST /api/v1/tax-reports/upload - 201 (150ms)
```

### 第三步：识别问题点

根据日志序列，可以定位问题：

#### ❌ 情况1：没有任何 🌐 日志
**问题**：请求根本没有到达后端

**可能原因**：
1. 后端服务没有启动
2. 前端请求的 URL/端口 错误
3. 网络问题
4. 前端代码没有正确执行

**解决方案**：
1. 检查后端服务状态
2. 检查前端的 `API_BASE` 配置
3. 检查浏览器控制台的网络请求
4. 检查是否有 JavaScript 错误阻止请求发送

#### ❌ 情况2：有 🌐 但没有 🏠 日志
**问题**：请求到达后端但被某个中间件拦截

**可能原因**：
1. CORS 问题（虽然配置了 allow all）
2. 请求被代理拦截

**解决方案**：
检查网络请求详情，看是否有 CORS 错误

#### ❌ 情况3：有 🏠 但没有 ✅ 日志
**问题**：JWT Token 解析失败

**可能原因**：
1. Token 缺失
2. Token 过期
3. Token 格式错误

**查看详情**：
- ❌ `[Tenant] Token expired` → Token 已过期，需要重新登录
- ❌ `[Tenant] Token invalid` → Token 格式错误
- ❌ `[Tenant] Missing tenant_id` → Token 中没有 tenant_id

**解决方案**：
1. 清除 localStorage 中的 token
2. 重新登录获取新 token

#### ❌ 情况4：有 ✅ 但没有 ⚡ 日志
**问题**：TenantContextMiddleware 抛出了异常

**可能原因**：
查看之前的错误日志

**解决方案**：
查看具体的异常堆栈跟踪

#### ❌ 情况5：有 ⚡ 但看到 `Rate limited`
**问题**：请求被限流拦截

**可能原因**：
1. 超过了请求频率限制
2. 限流配置过于严格

**解决方案**：
1. 等待一段时间后再试
2. 修改限流配置（在 `rate_limit_middleware.py` 中）

#### ❌ 情况6：有 ⚡ 但没有 📤 日志
**问题**：请求通过了限流中间件，但没有到达上传端点

**可能原因**：
1. 路由配置问题
2. 其他未知的中间件拦截

**解决方案**：
检查路由配置和中间件顺序

#### ❌ 情况7：有 📤 但卡在某一步
**问题**：到达了上传端点，但在某个步骤卡住

**诊断方法**：
根据卡住的步骤判断：
- Step 1 卡住 → 文件读取问题
- Step 2 卡住 → 文件保存问题（可能是磁盘满、权限问题）
- Step 3 卡住 → 数据库记录创建问题
- Step 4 卡住 → 数据库提交问题（可能是连接池耗尽、数据库锁）
- Step 5 卡住 → 后台任务创建问题

### 第四步：常见问题快速修复

#### 问题1：Token 过期
```
❌ [Tenant] Token expired
```
**解决**：
1. 打开浏览器开发者工具 → Application → Local Storage
2. 删除 `rag_token` 项
3. 刷新页面，重新登录

#### 问题2：限流拦截
```
⏳ [RateLimit] Rate limited: key=user:xxx, path=/api/v1/tax-reports/upload, retry_after=60s
```
**解决**：
等待 60 秒后再试，或联系管理员调整限流配置

#### 问题3：数据库连接池耗尽
如果看到 Step 4 耗时很长（>10秒），可能是连接池问题

**解决**：
1. 检查数据库连接数
2. 增加连接池大小（修改 `rag_backend/app/db/session.py`）
3. 检查是否有长时间运行的事务

#### 问题4：后端服务未启动
**解决**：
```bash
cd rag_backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 📊 日志标记说明

### HTTP 层
- 🌐 `[HTTP]` → 所有 HTTP 请求的入口和出口
- ✅ `[HTTP]` → 请求成功完成
- ❌ `[HTTP]` → 请求执行出错

### 中间件层
- 🏠 `[Tenant]` → 租户上下文中间件
- ⚡ `[RateLimit]` → 限流中间件

### 业务层
- 📤 `[TaxUpload]` → 上传端点
- ⏱️ `[TaxUpload]` → 性能日志
- 🔄 `[Background]` → 后台处理任务

## 🛠️ 调试技巧

### 1. 使用 curl 测试后端

```bash
# 先获取一个有效的 token
# 然后测试上传

curl -X POST "http://localhost:8000/api/v1/tax-reports/upload?tax_type=VAT" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "file=@your_file.pdf"
```

### 2. 检查浏览器网络请求

1. 打开开发者工具 (F12)
2. 切换到 Network 标签
3. 上传文件
4. 查看请求详情：
   - Status: 是什么状态码？
   - Response: 返回了什么内容？
   - Timing: 耗时多久？

### 3. 前端调试

在 `rag_frontend/src/api/tax-report.ts` 中添加更多日志：

```typescript
xhr.onerror = () => {
  console.error('📤 [TaxUpload] 网络错误', xhr.status, xhr.statusText)
  console.error('📤 [TaxUpload] Response:', xhr.responseText)
  reject(new Error('网络错误，请检查网络连接'))
}
```

### 4. 查看后端完整日志

```bash
cd rag_backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug
```

## 📞 如果以上都不起作用

1. **确认后端完全重启**：停止后端服务（Ctrl+C），然后重新启动
2. **清除浏览器缓存**：硬刷新 (Ctrl+Shift+R)
3. **检查后端错误日志**：向上滚动查看是否有任何异常
4. **重新构建前端**：如果前端有改动
5. **检查端口占用**：确保没有其他进程占用 8000 端口

## ✅ 确认问题已修复

修复后，应该看到完整的日志序列，且上传在 1 秒内完成：

```
🌐 [HTTP] POST /api/v1/tax-reports/upload - Request ID: xxx
🏠 [Tenant] Processing: POST /api/v1/tax-reports/upload
✅ [Tenant] Context set: tenant=xxx, user=xxx
⚡ [RateLimit] Allowed: POST /api/v1/tax-reports/upload (key=user:xxx)
📤 [TaxUpload] 收到上传请求: xxx.pdf, 大小: xxx
⏱️ [TaxUpload] Step 1: 开始读取文件内容... 0.01s
⏱️ [TaxUpload] Step 2: 开始保存文件到磁盘... 0.05s
⏱️ [TaxUpload] Step 3: 开始创建数据库记录... 0.06s
⏱️ [TaxUpload] Step 4: 开始提交数据库事务... 0.08s
⏱️ [TaxUpload] 数据库提交完成，耗时: 0.10s
✅ [TaxUpload] 数据库记录已创建: xxx
⏱️ [TaxUpload] Step 5: 创建后台处理任务... 0.11s
🚀 [TaxUpload] 快速返回: 报告ID=xxx, 总耗时: 0.15s
✅ [HTTP] POST /api/v1/tax-reports/upload - 201 (150ms)
```

## 🚀 性能基准

- **Step 1 (文件读取)**: < 0.1s
- **Step 2 (文件保存)**: < 0.5s
- **Step 3 (数据库记录)**: < 0.1s
- **Step 4 (数据库提交)**: < 1s
- **总耗时**: < 2s

如果任何步骤超过以上时间，说明存在问题需要调查。
