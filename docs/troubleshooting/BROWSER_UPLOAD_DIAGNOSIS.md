# 🔍 浏览器上传问题诊断指南

## 问题：上传请求没有到达后端

### 请执行以下诊断步骤

#### 步骤 1：打开浏览器开发者工具

1. 按 **F12** 打开开发者工具
2. 切换到 **Network（网络）** 标签
3. 选择 **Fetch/XHR** 过滤器（而不是 All）

#### 步骤 2：设置过滤器

在 Network 面板的过滤器输入框中输入：
```
tax-reports
```

#### 步骤 3：执行上传操作

1. 在税务提交页面选择文件
2. 点击上传按钮
3. **立即观察 Network 面板**

#### 步骤 4：检查请求状态

**请告诉我你看到了什么：**

##### 选项 A：看到了 `upload` 请求 ✅
- 请求显示什么状态？（Pending / 200 / 401 / 403 / 404 / ...）
- 请求的 Timing 是什么？
- 点击请求，查看 **Response** 标签

##### 选项 B：没有看到 `upload` 请求 ❌
- 请求可能被取消了
- 检查 Console 标签的错误信息
- 检查是否有红色的错误

##### 选项 C：看到请求但状态是 Pending ⏳
- 请求正在等待后端响应
- 检查后端容器日志：`docker logs -f rag_backend`

##### 选项 D：看到请求但状态是红色/失败 ❌
- **请截图或复制请求的详细信息**
- 状态码是什么？（401, 403, 404, 500, ...）
- 查看 Response 内容

---

## 备选诊断：检查 Token

#### 检查 localStorage 中的 Token

1. 打开浏览器开发者工具
2. 切换到 **Application** 标签
3. 在左侧菜单中选择 **Local Storage** → `http://127.0.0.1:5173`（或你的前端地址）
4. 查找 `rag_token` 或 `access_token`
5. **复制 Token 的前 20 个字符**

Token 应该是类似这样的格式：
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

如果 Token 为空或格式不对，说明用户没有登录！

---

## 快速测试：使用 curl 直接测试

```powershell
# 先获取一个有效的 Token（如果你有的话）
$token = "你的有效token"

# 测试上传路由
curl.exe -X POST "http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT" `
  -H "Authorization: Bearer $token" `
  -F "file=@test.pdf"
```

---

## 最可能的问题

根据分析，最可能的问题是：

### 1. Token 问题
**检查：** localStorage 中是否有有效的 `rag_token`

**如果 Token 无效或过期：**
- 后端会返回 401 Unauthorized
- 但不会记录详细日志（因为请求没有到达路由处理器）

### 2. 文件太大
**检查：** 上传的文件大小
- 最大限制：50MB
- 如果文件接近或超过这个限制，可能导致超时

### 3. 网络请求被取消
**检查：** Console 中是否有任何错误
- 如果有 JS 错误，可能导致请求被取消

---

## 请提供以下信息

1. **Network 面板**：是否有 tax-reports/upload 请求？
2. **Token**：localStorage 中的 rag_token 是什么？
3. **Console**：有任何红色错误吗？
4. **文件信息**：上传的文件名和大小？

提供这些信息后，我可以更准确地定位问题！
