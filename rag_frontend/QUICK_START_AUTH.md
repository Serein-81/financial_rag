# 🚀 登录注册功能快速开始

## 📋 功能概览

本系统支持两种用户类型：
- **普通用户**：个人或企业员工，可选使用企业邀请码加入团队
- **企业管理员**：创建企业账号，可生成邀请码邀请员工加入

## 🔑 API 端点

### 认证相关
```
POST /api/v1/auth/register          # 普通用户注册
POST /api/v1/auth/register/admin    # 企业管理员注册
POST /api/v1/auth/login              # 用户登录
GET  /api/v1/auth/me                 # 获取当前用户信息
```

### 知识库管理
```
GET    /api/v1/knowledge/bases                    # 获取知识库列表
POST   /api/v1/knowledge/bases                    # 创建知识库
DELETE /api/v1/knowledge/bases/{kb_id}            # 删除知识库
GET    /api/v1/knowledge/bases/{kb_id}/documents  # 获取文档列表
POST   /api/v1/knowledge/bases/{kb_id}/upload     # 上传文档
```

## 🎯 使用流程

### 1. 普通用户注册（无邀请码）
```typescript
// 请求
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "张三"
}

// 响应
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user_name": "张三"
}
```

### 1.1 普通用户注册（使用企业邀请码）
```typescript
// 请求
POST /api/v1/auth/register?invite_code=COMPANY-INVITE-CODE-123
Content-Type: application/json

{
  "email": "employee@example.com",
  "password": "password123",
  "full_name": "王五"
}

// 响应
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user_name": "王五"
}
```

### 2. 企业管理员注册（不需要邀请码）
```typescript
// 请求
POST /api/v1/auth/register/admin
Content-Type: application/json

{
  "email": "admin@company.com",
  "password": "password123",
  "full_name": "李四",
  "company_name": "某某科技有限公司"
}

// 响应
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user_name": "李四"
}
```

### 3. 用户登录
```typescript
// 请求
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

// 响应
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user_name": "张三"
}
```

### 4. 访问受保护的 API
```typescript
// 所有需要认证的请求都需要携带 Token
GET /api/v1/knowledge/bases
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

## 🖥️ 前端页面

### 路由配置
```
/login              # 登录页面
/register           # 注册页面（支持普通用户和企业管理员）
/                   # 首页（需要登录）
/knowledge          # 知识库管理（需要登录）
/upload             # 文档上传（需要登录）
/search             # 搜索页面（需要登录）
/documents          # 文档列表（需要登录）
/profile            # 个人资料（需要登录）
```

### 路由守卫
- 未登录用户访问受保护页面 → 自动跳转到 `/login`
- 已登录用户访问登录/注册页 → 自动跳转到 `/`

## 💾 数据存储

### localStorage
```typescript
rag_token          // JWT Token
rag_user_name      // 用户名
rag_user_email     // 用户邮箱
rag_user_role      // 用户角色（admin/normal）
rag_avatar_url     // 用户头像 URL
```

## 🎨 UI 组件

### 注册页面特性
1. **用户类型选择器**
   - 普通用户：个人使用图标
   - 企业管理员：企业图标

2. **条件表单**
   - 普通用户：姓名、邮箱、密码、确认密码、企业邀请码（可选）
   - 企业管理员：姓名、邮箱、密码、确认密码、企业名称（必填）

3. **实时验证**
   - 邮箱格式验证
   - 密码长度验证（≥6位）
   - 密码一致性验证
   - 邀请码为可选项（普通用户）

### 知识库管理页面特性
1. **左侧面板**
   - 知识库列表
   - 新建知识库按钮
   - 删除知识库功能

2. **右侧面板**
   - 文档列表表格
   - 上传文档按钮
   - 拖拽上传支持
   - 文档处理状态显示

3. **智能轮询**
   - 自动检测 pending/processing 状态
   - 每 3 秒刷新一次
   - 完成后自动停止

## 🔧 开发调试

### 检查登录状态
```typescript
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
console.log('是否登录:', authStore.isLoggedIn)
console.log('用户名:', authStore.userName)
console.log('Token:', authStore.token)
```

### 手动登出
```typescript
const authStore = useAuthStore()
authStore.logout()
router.push('/login')
```

### 获取 Token
```typescript
import { getToken } from '@/utils/request'

const token = getToken()
console.log('当前 Token:', token)
```

## 🐛 常见问题

### 1. 登录后仍然跳转到登录页
**原因**：Token 未正确保存
**解决**：检查 localStorage 中是否有 `rag_token`

### 2. API 请求返回 401
**原因**：Token 过期或无效
**解决**：重新登录获取新 Token

### 3. 企业管理员注册失败
**原因**：邮箱或手机号已被注册
**解决**：使用其他邮箱或手机号注册

### 4. 普通用户使用邀请码失败
**原因**：邀请码无效、已过期或已用完
**解决**：联系企业管理员获取新的邀请码

### 5. 文档上传后状态一直是 pending
**原因**：后端处理队列繁忙
**解决**：等待轮询自动刷新，或手动点击刷新按钮

## 📞 技术支持

如有问题，请查看：
- `rag_frontend/AUTH_IMPLEMENTATION_SUMMARY.md` - 完整实现总结
- `rag_backend/api-docs.md` - 后端 API 文档
- `API完整文档.md` - 完整 API 文档

## ✅ 测试清单

- [ ] 普通用户注册（无邀请码，创建个人账号）
- [ ] 普通用户注册（使用邀请码，加入企业团队）
- [ ] 企业管理员注册（不需要邀请码）
- [ ] 用户登录
- [ ] 未登录访问受保护页面（应跳转到登录页）
- [ ] 已登录访问登录页（应跳转到首页）
- [ ] 创建知识库
- [ ] 上传文档
- [ ] 查看文档处理状态
- [ ] 删除知识库
- [ ] 用户登出
