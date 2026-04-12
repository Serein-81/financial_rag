# 租户设置功能实现总结

## 📋 实现概述

为企业管理员提供完整的企业配置管理能力，包括企业信息、系统限制、功能开关、主题定制等。

## 📁 新增文件

### 1. 数据库模型
- **文件**: [tenant_settings.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/models/tenant_settings.py)
- **描述**: SQLAlchemy ORM 模型，定义租户设置表结构
- **功能**: 存储企业的所有配置信息

### 2. Pydantic Schemas
- **文件**: [tenant_settings.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/schemas/tenant_settings.py)
- **描述**: 数据验证和序列化
- **包含**:
  - `TenantSettingsCreate` - 创建Schema
  - `TenantSettingsUpdate` - 更新Schema
  - `TenantSettingsResponse` - 响应Schema
  - `TenantSettingsPublicResponse` - 公开响应Schema
  - `FeatureToggleRequest` - 功能开关请求
  - `TenantSettingsListResponse` - 列表响应

### 3. 业务服务层
- **文件**: [tenant_settings_service.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/services/tenant_settings_service.py)
- **描述**: 业务逻辑层，处理租户设置的 CRUD 操作
- **核心方法**:
  - `get_settings_by_tenant_id()` - 获取租户设置
  - `create_settings()` - 创建租户设置
  - `update_settings()` - 更新租户设置
  - `delete_settings()` - 删除租户设置
  - `toggle_feature()` - 切换功能开关
  - `initialize_settings_for_tenant()` - 初始化租户设置
  - `check_feature_enabled()` - 检查功能是否启用

### 4. API 端点
- **文件**: [tenant_settings.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/api/v1/endpoints/tenant_settings.py)
- **描述**: FastAPI 路由定义
- **包含**: 11 个 API 端点

### 5. 数据库迁移脚本
- **创建表脚本**: [create_tenant_settings_table.sql](file:///d:/Python/Codebase/My_rag/rag_backend/sql/create_tenant_settings_table.sql)
- **初始化脚本**: [initialize_tenant_settings.sql](file:///d:/Python/Codebase/My_rag/rag_backend/sql/initialize_tenant_settings.sql)

### 6. 文档
- **快速启动指南**: [QUICKSTART_TENANT_SETTINGS.md](file:///d:/Python/Codebase/My_rag/rag_backend/QUICKSTART_TENANT_SETTINGS.md)
- **API 使用指南**: [docs/tenant_settings_api.md](file:///d:/Python/Codebase/My_rag/rag_backend/docs/tenant_settings_api.md)

### 7. 测试脚本
- **文件**: [test_tenant_settings.py](file:///d:/Python/Codebase/My_rag/rag_backend/test_tenant_settings.py)
- **用途**: 验证 API 是否正常工作

## 🔧 修改的文件

### 1. 模型导出
- **文件**: [models/__init__.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/models/__init__.py)
- **修改**: 添加 `TenantSettings` 模型导出

### 2. 应用入口
- **文件**: [main.py](file:///d:/Python/Codebase/My_rag/rag_backend/app/main.py)
- **修改**:
  - 添加 `tenant_settings` 模型导入
  - 添加 `tenant_settings` 路由导入
  - 注册租户设置路由

## 🗄️ 数据库表结构

```sql
CREATE TABLE tenant_settings (
    -- 基础字段
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    -- 企业基本信息
    company_name VARCHAR(200) NOT NULL,
    company_logo VARCHAR(500),
    company_description TEXT,
    company_website VARCHAR(500),
    company_address VARCHAR(500),
    company_phone VARCHAR(50),
    company_email VARCHAR(255),

    -- 管理员信息
    admin_name VARCHAR(100),
    admin_email VARCHAR(255),
    admin_phone VARCHAR(50),

    -- 系统限制
    max_users INTEGER DEFAULT 10,
    max_storage_gb INTEGER DEFAULT 100,
    max_knowledge_bases INTEGER DEFAULT 10,
    max_documents INTEGER DEFAULT 1000,
    max_monthly_requests INTEGER,

    -- 功能开关
    enable_group_chat BOOLEAN DEFAULT TRUE,
    enable_multi_agent BOOLEAN DEFAULT TRUE,
    enable_knowledge_graph BOOLEAN DEFAULT FALSE,
    enable_human_review BOOLEAN DEFAULT TRUE,
    enable_audit BOOLEAN DEFAULT FALSE,
    enable_tax_report BOOLEAN DEFAULT FALSE,
    enable_financial_data BOOLEAN DEFAULT FALSE,

    -- 主题设置
    primary_color VARCHAR(20) DEFAULT '#1890ff',
    secondary_color VARCHAR(20),
    custom_css TEXT,
    custom_footer TEXT,

    -- 通知设置
    email_notification BOOLEAN DEFAULT TRUE,
    system_notification BOOLEAN DEFAULT TRUE,
    notification_email VARCHAR(255),

    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    is_trial BOOLEAN DEFAULT TRUE,
    trial_expires_at TIMESTAMP,

    -- 扩展数据
    extra_settings JSONB
);
```

## 🔐 权限控制

### 普通用户
- ✅ 查看企业设置
- ✅ 查看公开信息
- ✅ 检查功能状态

### 企业管理员
- ✅ 所有普通用户权限
- ✅ 更新企业设置
- ✅ 初始化企业设置
- ✅ 切换功能开关
- ✅ 查看所有租户设置
- ✅ 更新任意租户设置
- ✅ 删除租户设置
- ✅ 创建租户设置

## 📡 API 端点列表

| 方法 | 端点 | 描述 | 权限 |
|------|------|------|------|
| GET | `/me` | 获取当前企业设置 | 所有用户 |
| PUT | `/me` | 更新当前企业设置 | 管理员 |
| GET | `/public/{tenant_id}` | 获取公开信息 | 公开 |
| GET | `/` | 获取所有租户设置 | 管理员 |
| POST | `/` | 创建租户设置 | 管理员 |
| GET | `/{tenant_id}` | 获取指定租户设置 | 管理员 |
| PUT | `/{tenant_id}` | 更新指定租户设置 | 管理员 |
| DELETE | `/{tenant_id}` | 删除租户设置 | 管理员 |
| POST | `/feature-toggle` | 切换功能开关 | 管理员 |
| GET | `/features/check` | 检查功能状态 | 所有用户 |
| POST | `/initialize` | 初始化企业设置 | 管理员 |

## 🚀 部署步骤

### 1. 执行数据库迁移

```bash
cd rag_backend

# 创建租户设置表
psql -U postgres -d your_database -f sql/create_tenant_settings_table.sql

# 为现有租户初始化默认设置
psql -U postgres -d your_database -f sql/initialize_tenant_settings.sql
```

### 2. 重启后端服务

```bash
# 如果使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或者使用 docker-compose
docker-compose restart backend
```

### 3. 验证部署

访问 API 文档查看所有端点:
```
http://localhost:8000/docs
```

## 💡 使用示例

### 场景 1: 企业管理员修改企业名称

```bash
curl -X PUT "http://localhost:8000/api/v1/tenant-settings/me" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "新公司名称",
    "company_phone": "400-123-4567"
  }'
```

### 场景 2: 启用知识图谱功能

```bash
curl -X POST "http://localhost:8000/api/v1/tenant-settings/feature-toggle" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "enable_knowledge_graph",
    "enabled": true
  }'
```

### 场景 3: 管理员为新企业创建设置

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

## 🎯 功能特性

### ✅ 企业信息管理
- 修改企业名称
- 上传企业Logo
- 添加企业描述和网站
- 设置联系方式

### ✅ 系统限制配置
- 最大用户数
- 存储空间限制
- 知识库数量限制
- 文档数量限制
- 月度请求次数限制

### ✅ 功能开关
- 群聊功能
- 多Agent功能
- 知识图谱
- 人工审核
- 审计功能
- 税务报表
- 财务数据

### ✅ 主题定制
- 主色调
- 次要色调
- 自定义CSS
- 自定义页脚

### ✅ 通知设置
- 邮件通知
- 系统通知
- 通知邮箱

## 🔍 功能开关使用场景

### 1. 知识图谱
```python
# 在知识图谱功能中检查开关
from app.services.tenant_settings_service import tenant_settings_service

if not await tenant_settings_service.check_feature_enabled(
    user.tenant_id,
    'enable_knowledge_graph'
):
    raise HTTPException(status_code=403, detail="知识图谱功能未启用")
```

### 2. 群聊功能
```python
# 在群聊功能中检查开关
from app.services.tenant_settings_service import tenant_settings_service

if not await tenant_settings_service.check_feature_enabled(
    user.tenant_id,
    'enable_group_chat'
):
    raise HTTPException(status_code=403, detail="群聊功能未启用")
```

### 3. 多Agent功能
```python
# 在多Agent功能中检查开关
from app.services.tenant_settings_service import tenant_settings_service

if not await tenant_settings_service.check_feature_enabled(
    user.tenant_id,
    'enable_multi_agent'
):
    raise HTTPException(status_code=403, detail="多Agent功能未启用")
```

## 📊 性能考虑

- ✅ 数据库已创建索引（tenant_id, company_name）
- ✅ 异步数据库操作
- ✅ 合理的字段长度限制
- ✅ 自动更新 updated_at 字段
- ⚠️ 大规模部署时建议启用 Redis 缓存

## 🔒 安全特性

- ✅ Pydantic 数据验证
- ✅ 权限控制（管理员）
- ✅ 敏感信息隐藏（公开接口）
- ✅ 输入长度限制
- ✅ SQL 注入防护（使用 SQLAlchemy ORM）
- ✅ XSS 防护（前端渲染）

## 📝 扩展建议

### 添加新字段
1. 在 `app/models/tenant_settings.py` 中添加字段
2. 在 `app/schemas/tenant_settings.py` 中添加验证
3. 在 `sql/create_tenant_settings_table.sql` 中添加 ALTER TABLE 语句
4. 更新前端表单和文档

### 添加新功能开关
1. 在模型中添加布尔字段
2. 在 Schema 中添加验证
3. 在 `FeatureToggleRequest` 的 `valid_features` 列表中添加功能名称
4. 更新权限控制和文档

## 🐛 故障排查

### 常见问题

**Q1: API 返回 404**
- 检查路由是否正确注册
- 检查 main.py 中是否导入了 tenant_settings

**Q2: 数据库错误**
- 检查是否执行了数据库迁移
- 检查数据库连接配置

**Q3: 权限错误**
- 检查用户是否为管理员
- 检查 Token 是否有效

**Q4: 功能开关不生效**
- 检查是否正确调用了 `check_feature_enabled()`
- 检查租户 ID 是否正确

## 📞 技术支持

如有问题，请检查：
1. 数据库迁移是否成功
2. API 文档是否正确加载（访问 `/docs`）
3. 日志中的错误信息
4. 权限配置是否正确

---

**版本**: 1.0.0
**创建日期**: 2026-04-01
**状态**: ✅ 已完成
**维护者**: 企业管理员
