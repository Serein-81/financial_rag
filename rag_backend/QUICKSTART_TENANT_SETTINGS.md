# 租户设置功能 - 快速启动指南

## 1. 部署步骤

### 步骤 1: 执行数据库迁移

```bash
cd rag_backend

# 创建租户设置表
psql -U postgres -d your_database -f sql/create_tenant_settings_table.sql

# 为现有租户初始化默认设置
psql -U postgres -d your_database -f sql/initialize_tenant_settings.sql
```

### 步骤 2: 重启后端服务

```bash
# 如果使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或者使用 docker-compose
docker-compose restart backend
```

## 2. 验证部署

### 测试 API 端点

```bash
# 1. 获取 Token（假设您已经配置了认证）

# 2. 获取当前企业的设置
curl -X GET "http://localhost:8000/api/v1/tenant-settings/me" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. 初始化企业设置（如果还没有设置）
curl -X POST "http://localhost:8000/api/v1/tenant-settings/initialize?company_name=测试公司" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. 更新企业设置
curl -X PUT "http://localhost:8000/api/v1/tenant-settings/me" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "新公司名称",
    "company_phone": "400-123-4567"
  }'
```

## 3. 功能清单

✅ **企业基本信息管理**
- 修改企业名称
- 上传企业Logo
- 添加企业描述和网站
- 设置联系方式

✅ **系统限制配置**
- 最大用户数
- 存储空间限制
- 知识库数量限制
- 文档数量限制

✅ **功能开关**
- 启用/禁用群聊
- 启用/禁用多Agent
- 启用/禁用知识图谱
- 启用/禁用人工审核
- 启用/禁用审计功能
- 启用/禁用税务报表
- 启用/禁用财务数据

✅ **主题定制**
- 自定义主色调
- 自定义次要色调
- 添加自定义CSS
- 添加自定义页脚

✅ **通知设置**
- 邮件通知开关
- 系统通知开关
- 通知邮箱配置

## 4. 权限说明

| 功能 | 普通用户 | 企业管理员 |
|------|---------|-----------|
| 查看企业设置 | ✅ | ✅ |
| 查看公开信息 | ✅ | ✅ |
| 检查功能状态 | ✅ | ✅ |
| 更新企业设置 | ❌ | ✅ |
| 初始化企业 | ❌ | ✅ |
| 切换功能开关 | ❌ | ✅ |
| 管理所有租户 | ❌ | ✅ |

## 5. 常见问题

### Q1: 如何为新企业创建设置？
A: 使用企业管理员账户调用 `POST /api/v1/tenant-settings/initialize` 接口进行初始化。

### Q2: 如何启用知识图谱功能？
A: 企业管理员调用 `POST /api/v1/tenant-settings/feature-toggle`，请求体为：
```json
{
  "feature": "enable_knowledge_graph",
  "enabled": true
}
```

### Q3: 普通用户可以查看哪些信息？
A: 普通用户只能通过 `/me` 接口查看自己企业的完整设置，通过 `/features/check` 查看功能开关状态。

### Q4: 如何限制企业用户数量？
A: 在企业设置中修改 `max_users` 字段即可。

## 6. 下一步

1. **前端开发**: 参考 `docs/tenant_settings_api.md` 中的前端集成建议
2. **功能控制**: 在其他功能模块中集成功能开关检查
3. **权限细化**: 根据需要调整权限控制逻辑
4. **监控**: 添加设置变更的审计日志

## 7. API 完整列表

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/tenant-settings/me` | 获取当前企业设置 |
| PUT | `/tenant-settings/me` | 更新当前企业设置 |
| GET | `/tenant-settings/public/{tenant_id}` | 获取公开信息 |
| GET | `/tenant-settings/` | 获取所有租户设置 |
| POST | `/tenant-settings/` | 创建租户设置 |
| GET | `/tenant-settings/{tenant_id}` | 获取指定租户设置 |
| PUT | `/tenant-settings/{tenant_id}` | 更新指定租户设置 |
| DELETE | `/tenant-settings/{tenant_id}` | 删除租户设置 |
| POST | `/tenant-settings/feature-toggle` | 切换功能开关 |
| GET | `/tenant-settings/features/check` | 检查功能状态 |
| POST | `/tenant-settings/initialize` | 初始化企业设置 |

## 8. 性能优化

- 数据库已创建索引，查询性能良好
- 建议启用 Redis 缓存热门设置
- 大规模部署时可考虑读写分离

## 9. 安全建议

1. 定期备份 `tenant_settings` 表
2. 监控异常的配置变更
3. 限制 `custom_css` 和 `custom_footer` 的长度
4. 定期审计权限配置

## 10. 技术支持

如有问题，请检查：
1. 数据库迁移是否成功
2. API 文档是否正确加载（访问 `/docs`）
3. 日志中的错误信息
4. 权限配置是否正确

---

**版本**: 1.0.0
**创建日期**: 2026-04-01
**维护者**: 企业管理员
