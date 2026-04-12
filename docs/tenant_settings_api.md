# 租户设置 API 使用指南

## 概述

租户设置功能为企业管理员提供了完整的企业配置管理能力，包括企业信息、系统限制、功能开关、主题定制等。

## 数据库迁移

### 1. 创建租户设置表

```bash
# 进入数据库目录
cd rag_backend

# 执行 SQL 脚本创建表
psql -U postgres -d your_database -f sql/create_tenant_settings_table.sql
```

### 2. 初始化现有租户的设置

```bash
# 为现有租户创建默认设置
psql -U postgres -d your_database -f sql/initialize_tenant_settings.sql
```

## API 端点

### 基础信息

- **前缀**: `/api/v1/tenant-settings`
- **认证**: 大部分接口需要管理员权限

### 1. 获取当前企业的设置

```
GET /api/v1/tenant-settings/me
```

**权限**: 所有已登录用户
**响应示例**:
```json
{
  "id": "uuid",
  "tenant_id": "tenant_001",
  "company_name": "示例公司",
  "company_logo": "https://example.com/logo.png",
  "company_description": "公司简介",
  "max_users": 10,
  "enable_group_chat": true,
  "enable_multi_agent": true,
  "primary_color": "#1890ff",
  ...
}
```

### 2. 更新当前企业的设置

```
PUT /api/v1/tenant-settings/me
```

**权限**: 企业管理员
**请求体**:
```json
{
  "company_name": "新公司名称",
  "company_logo": "https://example.com/new-logo.png",
  "max_users": 20,
  "primary_color": "#52c41a",
  "enable_knowledge_graph": true
}
```

### 3. 获取公开的企业信息

```
GET /api/v1/tenant-settings/public/{tenant_id}
```

**权限**: 公开接口，无需认证
**响应示例**:
```json
{
  "tenant_id": "tenant_001",
  "company_name": "示例公司",
  "company_logo": "https://example.com/logo.png",
  "company_description": "公司简介",
  "company_website": "https://example.com",
  "primary_color": "#1890ff",
  "secondary_color": "#ffffff"
}
```

### 4. 获取所有租户设置（管理员）

```
GET /api/v1/tenant-settings/?skip=0&limit=20
```

**权限**: 管理员
**响应示例**:
```json
{
  "settings": [...],
  "total": 100
}
```

### 5. 创建租户设置

```
POST /api/v1/tenant-settings/
```

**权限**: 企业管理员
**请求体**:
```json
{
  "tenant_id": "new_tenant",
  "company_name": "新公司",
  "max_users": 50
}
```

### 6. 获取指定租户的设置

```
GET /api/v1/tenant-settings/{tenant_id}
```

**权限**: 管理员

### 7. 更新指定租户的设置

```
PUT /api/v1/tenant-settings/{tenant_id}
```

**权限**: 管理员

### 8. 删除租户设置（管理员）

```
DELETE /api/v1/tenant-settings/{tenant_id}
```

**权限**: 管理员

### 9. 切换功能开关

```
POST /api/v1/tenant-settings/feature-toggle
```

**权限**: 企业管理员
**请求体**:
```json
{
  "feature": "enable_knowledge_graph",
  "enabled": true
}
```

**可用功能列表**:
- `enable_group_chat` - 群聊功能
- `enable_multi_agent` - 多Agent功能
- `enable_knowledge_graph` - 知识图谱
- `enable_human_review` - 人工审核
- `enable_audit` - 审计功能
- `enable_tax_report` - 税务报表
- `enable_financial_data` - 财务数据

### 10. 检查功能开关状态

```
GET /api/v1/tenant-settings/features/check
```

**权限**: 所有已登录用户
**响应示例**:
```json
{
  "tenant_id": "tenant_001",
  "features": {
    "enable_group_chat": true,
    "enable_multi_agent": true,
    "enable_knowledge_graph": false,
    "enable_human_review": true,
    "enable_audit": false,
    "enable_tax_report": false,
    "enable_financial_data": false
  }
}
```

### 11. 初始化企业设置

```
POST /api/v1/tenant-settings/initialize?company_name=公司名称&admin_email=admin@example.com
```

**权限**: 企业管理员

## 可配置的字段

### 企业基本信息
- `company_name` - 企业名称（必填）
- `company_logo` - 企业Logo URL
- `company_description` - 企业描述
- `company_website` - 企业网站
- `company_address` - 企业地址
- `company_phone` - 联系电话
- `company_email` - 联系邮箱

### 管理员信息
- `admin_name` - 管理员姓名
- `admin_email` - 管理员邮箱
- `admin_phone` - 管理员电话

### 系统限制
- `max_users` - 最大用户数（1-1000）
- `max_storage_gb` - 最大存储空间(GB)（1-10000）
- `max_knowledge_bases` - 最大知识库数量（1-100）
- `max_documents` - 最大文档数量（1-100000）
- `max_monthly_requests` - 最大月度请求次数

### 功能开关
- `enable_group_chat` - 是否启用群聊
- `enable_multi_agent` - 是否启用多Agent
- `enable_knowledge_graph` - 是否启用知识图谱
- `enable_human_review` - 是否启用人工审核
- `enable_audit` - 是否启用审计功能
- `enable_tax_report` - 是否启用税务报表
- `enable_financial_data` - 是否启用财务数据

### 主题设置
- `primary_color` - 主色调（默认 #1890ff）
- `secondary_color` - 次要色调
- `custom_css` - 自定义CSS
- `custom_footer` - 自定义页脚

### 通知设置
- `email_notification` - 是否启用邮件通知
- `system_notification` - 是否启用系统通知
- `notification_email` - 通知接收邮箱

## 权限说明

### 普通用户
- ✅ GET /me - 查看企业设置
- ✅ GET /public/{tenant_id} - 查看公开信息
- ✅ GET /features/check - 检查功能状态

### 企业管理员
- ✅ 所有普通用户权限
- ✅ PUT /me - 更新企业设置
- ✅ POST /initialize - 初始化企业设置
- ✅ POST /feature-toggle - 切换功能开关
- ✅ GET / - 查看所有租户设置
- ✅ GET /{tenant_id} - 查看任意租户设置
- ✅ PUT /{tenant_id} - 更新任意租户设置
- ✅ DELETE /{tenant_id} - 删除租户设置
- ✅ POST / - 创建租户设置

## 集成建议

### 1. 前端集成

创建 API 调用模块:

```typescript
// api/tenant-settings.ts
import request from '@/utils/request'

export const getMyTenantSettings = () => {
  return request.get('/tenant-settings/me')
}

export const updateMyTenantSettings = (data: any) => {
  return request.put('/tenant-settings/me', data)
}

export const checkFeatures = () => {
  return request.get('/tenant-settings/features/check')
}

export const toggleFeature = (feature: string, enabled: boolean) => {
  return request.post('/tenant-settings/feature-toggle', { feature, enabled })
}
```

### 2. 初始化钩子

在用户注册/企业创建时自动初始化设置:

```python
from app.services.tenant_settings_service import tenant_settings_service

async def on_tenant_created(tenant_id: str, company_name: str, admin_email: str):
    await tenant_settings_service.initialize_settings_for_tenant(
        tenant_id=tenant_id,
        company_name=company_name,
        admin_email=admin_email
    )
```

### 3. 功能访问控制

在需要的地方检查功能开关:

```python
from app.services.tenant_settings_service import tenant_settings_service

async def my_feature(user: User):
    if not await tenant_settings_service.check_feature_enabled(
        user.tenant_id,
        'enable_knowledge_graph'
    ):
        raise HTTPException(
            status_code=403,
            detail="知识图谱功能未启用"
        )
```

## 注意事项

1. **UUID 生成**: 确保数据库已启用 uuid-ossp 扩展
2. **权限控制**: 敏感操作需要管理员权限
3. **数据验证**: 所有输入都经过 Pydantic 验证
4. **错误处理**: 使用 HTTPException 返回友好的错误信息
5. **日志记录**: 所有操作都有日志记录

## 数据库索引

已创建的索引:
- `idx_tenant_settings_tenant_id` - 租户ID（唯一）
- `idx_tenant_settings_company_name` - 企业名称

## 扩展功能

如果需要添加新的设置字段:

1. 在 `app/models/tenant_settings.py` 中添加字段
2. 在 `app/schemas/tenant_settings.py` 中添加验证
3. 在 `sql/create_tenant_settings_table.sql` 中添加 ALTER TABLE 语句
4. 更新前端表单和文档

## 示例场景

### 场景1: 企业管理员修改企业名称

```bash
curl -X PUT "http://localhost:8000/api/v1/tenant-settings/me" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "新公司名称"
  }'
```

### 场景2: 管理员为新企业创建设置

```bash
curl -X POST "http://localhost:8000/api/v1/tenant-settings/" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "new_company",
    "company_name": "新公司",
    "max_users": 50,
    "enable_multi_agent": true
  }'
```

### 场景3: 切换功能开关

```bash
curl -X POST "http://localhost:8000/api/v1/tenant-settings/feature-toggle" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "enable_knowledge_graph",
    "enabled": true
  }'
```
