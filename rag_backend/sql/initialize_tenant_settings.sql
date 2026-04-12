-- 初始化租户设置脚本
-- 此脚本为现有租户创建默认设置

-- 将您的数据库名称替换到下面
-- \c your_database;

-- 为所有现有租户创建默认设置
INSERT INTO tenant_settings (tenant_id, company_name, is_trial, max_users, max_storage_gb, enable_group_chat, enable_multi_agent, primary_color)
SELECT DISTINCT
    u.tenant_id,
    COALESCE(u.company_name, '默认企业'),
    TRUE,
    10,
    100,
    TRUE,
    TRUE,
    '#1890ff'
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM tenant_settings ts WHERE ts.tenant_id = u.tenant_id
)
ON CONFLICT (tenant_id) DO NOTHING;

-- 验证初始化结果
SELECT
    ts.tenant_id,
    ts.company_name,
    ts.is_trial,
    ts.max_users,
    ts.enable_group_chat,
    ts.enable_multi_agent,
    ts.primary_color,
    COUNT(u.id) as user_count
FROM tenant_settings ts
LEFT JOIN users u ON u.tenant_id = ts.tenant_id
GROUP BY ts.tenant_id, ts.company_name, ts.is_trial, ts.max_users, ts.enable_group_chat, ts.enable_multi_agent, ts.primary_color
ORDER BY ts.created_at DESC;
