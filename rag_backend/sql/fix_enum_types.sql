-- ============================================
-- 修复财务健康模块枚举类型问题（完整版）
-- 处理默认值的类型转换问题
-- ============================================

-- 1. 先删除默认值
ALTER TABLE financial_health_reports ALTER COLUMN report_period DROP DEFAULT;
ALTER TABLE financial_health_reports ALTER COLUMN health_status DROP DEFAULT;

-- 2. 将列类型改为 VARCHAR（先移除枚举约束）
ALTER TABLE financial_health_reports ALTER COLUMN report_period TYPE VARCHAR USING report_period::text;
ALTER TABLE financial_health_reports ALTER COLUMN health_status TYPE VARCHAR USING health_status::text;

-- 3. 删除旧的枚举类型（如果存在）
DROP TYPE IF EXISTS reportperiod;
DROP TYPE IF EXISTS healthstatus;

-- 4. 创建新的枚举类型（使用小写值匹配 Python，包含所有可能的值）
CREATE TYPE reportperiod AS ENUM ('daily', 'weekly', 'monthly', 'quarterly', 'yearly');
CREATE TYPE healthstatus AS ENUM ('healthy', 'warning', 'critical', 'caution', 'unknown', 'excellent');

-- 5. 将列类型改回枚举（带显式转换）
ALTER TABLE financial_health_reports ALTER COLUMN report_period TYPE reportperiod USING report_period::reportperiod;
ALTER TABLE financial_health_reports ALTER COLUMN health_status TYPE healthstatus USING health_status::healthstatus;

-- 6. 验证枚举类型和值
SELECT typname, string_agg(enumlabel, ', ' ORDER BY enumsortorder) as enum_values
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname IN ('reportperiod', 'healthstatus')
GROUP BY typname;

-- 7. 验证数据
SELECT id, report_period, health_status FROM financial_health_reports LIMIT 10;
