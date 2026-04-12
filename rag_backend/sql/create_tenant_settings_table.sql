-- 创建租户设置表
-- 执行方式: psql -U postgres -d your_database -f create_tenant_settings_table.sql

-- 如果使用 UUID 类型，需要启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建 tenant_settings 表
CREATE TABLE IF NOT EXISTS tenant_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- 租户标识
    tenant_id VARCHAR(50) UNIQUE NOT NULL,

    -- 企业基本信息
    company_name VARCHAR(200) NOT NULL,
    company_logo VARCHAR(500),
    company_description TEXT,
    company_website VARCHAR(500),
    company_address VARCHAR(500),
    company_phone VARCHAR(50),
    company_email VARCHAR(255),

    -- 企业管理员信息
    admin_name VARCHAR(100),
    admin_email VARCHAR(255),
    admin_phone VARCHAR(50),

    -- 系统设置
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

    -- 主题和界面设置
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
    trial_expires_at TIMESTAMP WITH TIME ZONE,

    -- 扩展数据
    extra_settings JSONB
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_tenant_settings_tenant_id ON tenant_settings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_settings_company_name ON tenant_settings(company_name);

-- 添加注释
COMMENT ON TABLE tenant_settings IS '租户设置表 - 存储企业配置信息';
COMMENT ON COLUMN tenant_settings.tenant_id IS '租户ID';
COMMENT ON COLUMN tenant_settings.company_name IS '企业名称';
COMMENT ON COLUMN tenant_settings.company_logo IS '企业Logo URL';
COMMENT ON COLUMN tenant_settings.company_description IS '企业描述';
COMMENT ON COLUMN tenant_settings.company_website IS '企业网站';
COMMENT ON COLUMN tenant_settings.company_address IS '企业地址';
COMMENT ON COLUMN tenant_settings.company_phone IS '联系电话';
COMMENT ON COLUMN tenant_settings.company_email IS '联系邮箱';
COMMENT ON COLUMN tenant_settings.admin_name IS '管理员姓名';
COMMENT ON COLUMN tenant_settings.admin_email IS '管理员邮箱';
COMMENT ON COLUMN tenant_settings.admin_phone IS '管理员电话';
COMMENT ON COLUMN tenant_settings.max_users IS '最大用户数';
COMMENT ON COLUMN tenant_settings.max_storage_gb IS '最大存储空间(GB)';
COMMENT ON COLUMN tenant_settings.max_knowledge_bases IS '最大知识库数量';
COMMENT ON COLUMN tenant_settings.max_documents IS '最大文档数量';
COMMENT ON COLUMN tenant_settings.max_monthly_requests IS '最大月度请求次数';
COMMENT ON COLUMN tenant_settings.enable_group_chat IS '是否启用群聊';
COMMENT ON COLUMN tenant_settings.enable_multi_agent IS '是否启用多Agent';
COMMENT ON COLUMN tenant_settings.enable_knowledge_graph IS '是否启用知识图谱';
COMMENT ON COLUMN tenant_settings.enable_human_review IS '是否启用人工审核';
COMMENT ON COLUMN tenant_settings.enable_audit IS '是否启用审计功能';
COMMENT ON COLUMN tenant_settings.enable_tax_report IS '是否启用税务报表';
COMMENT ON COLUMN tenant_settings.enable_financial_data IS '是否启用财务数据';
COMMENT ON COLUMN tenant_settings.primary_color IS '主色调';
COMMENT ON COLUMN tenant_settings.secondary_color IS '次要色调';
COMMENT ON COLUMN tenant_settings.custom_css IS '自定义CSS';
COMMENT ON COLUMN tenant_settings.custom_footer IS '自定义页脚';
COMMENT ON COLUMN tenant_settings.email_notification IS '是否启用邮件通知';
COMMENT ON COLUMN tenant_settings.system_notification IS '是否启用系统通知';
COMMENT ON COLUMN tenant_settings.notification_email IS '通知接收邮箱';
COMMENT ON COLUMN tenant_settings.is_active IS '是否启用';
COMMENT ON COLUMN tenant_settings.is_trial IS '是否试用版';
COMMENT ON COLUMN tenant_settings.trial_expires_at IS '试用过期时间';
COMMENT ON COLUMN tenant_settings.extra_settings IS '额外设置(JSON)';

-- 创建一个函数来自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 创建触发器
DROP TRIGGER IF EXISTS update_tenant_settings_updated_at ON tenant_settings;
CREATE TRIGGER update_tenant_settings_updated_at
    BEFORE UPDATE ON tenant_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 验证表创建成功
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'tenant_settings'
ORDER BY ordinal_position;
