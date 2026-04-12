-- ==========================================
-- 财务模块测试数据脚本
-- 用于插入测试数据以验证功能
-- ==========================================

-- 1. 首先检查各表数据量
-- 在 Navicat 新建查询执行以下语句查看表记录数
SELECT 'user_financial_data' as table_name, COUNT(*) as row_count FROM user_financial_data
UNION ALL
SELECT 'financial_data_history', COUNT(*) FROM financial_data_history
UNION ALL
SELECT 'tax_reports', COUNT(*) FROM tax_reports
UNION ALL
SELECT 'tax_report_documents', COUNT(*) FROM tax_report_documents
UNION ALL
SELECT 'financial_health_reports', COUNT(*) FROM financial_health_reports
UNION ALL
SELECT 'financial_anomaly_records', COUNT(*) FROM financial_anomaly_records
UNION ALL
SELECT 'financial_trend_data', COUNT(*) FROM financial_trend_data
UNION ALL
SELECT 'financial_thresholds', COUNT(*) FROM financial_thresholds;

-- 2. 查看现有用户和租户信息（用于获取有效的 foreign key）
-- SELECT id, email, tenant_id FROM users LIMIT 5;

-- 3. 插入 user_financial_data 测试数据
-- 注意：请将下面的 'YOUR_USER_ID' 和 'YOUR_TENANT_ID' 替换为实际存在的值
/*
INSERT INTO user_financial_data (
    id,
    user_id,
    tenant_id,
    fiscal_year,
    fiscal_quarter,
    fiscal_month,
    total_revenue,
    operating_revenue,
    non_operating_revenue,
    total_expenses,
    operating_expenses,
    cost_of_goods_sold,
    gross_profit,
    operating_profit,
    net_profit,
    taxable_sales,
    vat_payable,
    corporate_income_tax,
    personal_income_tax,
    other_taxes,
    total_tax_burden,
    invoice_count,
    input_tax,
    output_tax,
    cash_balance,
    accounts_receivable,
    accounts_payable,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    id,
    tenant_id,
    2024,
    (EXTRACT(QUARTER FROM CURRENT_DATE))::int,
    (EXTRACT(MONTH FROM CURRENT_DATE))::int,
    random() * 10000000 + 1000000,  -- 总收入 100万-1100万
    random() * 9000000 + 900000,     -- 营业收入
    random() * 1000000,              -- 营业外收入
    random() * 8000000 + 800000,      -- 总支出
    random() * 6000000 + 600000,      -- 营业成本
    random() * 5000000 + 500000,      -- 销售成本
    random() * 3000000 + 300000,      -- 毛利润
    random() * 2000000 + 200000,     -- 营业利润
    random() * 1500000 + 150000,     -- 净利润
    random() * 5000000 + 500000,      -- 应税销售额
    random() * 500000 + 50000,       -- 增值税
    random() * 300000 + 30000,       -- 企业所得税
    random() * 100000 + 10000,       -- 个人所得税
    random() * 200000 + 20000,       -- 其他税金
    random() * 800000 + 80000,       -- 总税负
    (random() * 100 + 10)::int,      -- 发票数量
    random() * 400000 + 40000,       -- 进项税
    random() * 500000 + 50000,       -- 销项税
    random() * 5000000 + 500000,     -- 现金余额
    random() * 3000000 + 300000,     -- 应收账款
    random() * 2000000 + 200000,     -- 应付账款
    NOW(),
    NOW()
FROM users
LIMIT 5;
*/

-- 4. 插入 financial_health_reports 测试数据
/*
INSERT INTO financial_health_reports (
    id,
    user_id,
    tenant_id,
    report_name,
    report_period,
    period_start,
    period_end,
    overall_health_score,
    health_status,
    revenue_summary,
    expense_summary,
    profit_summary,
    financial_metrics,
    risk_assessments,
    recommendations,
    anomaly_detections,
    status,
    created_at,
    completed_at
)
SELECT
    gen_random_uuid(),
    id,
    tenant_id,
    '测试财务健康报告 - ' || CURRENT_DATE,
    'monthly',
    CURRENT_DATE - INTERVAL '30 days',
    CURRENT_DATE,
    random() * 40 + 60,  -- 健康评分 60-100
    CASE
        WHEN random() > 0.7 THEN 'healthy'
        WHEN random() > 0.4 THEN 'warning'
        ELSE 'critical'
    END,
    '{"total_revenue": 5000000, "revenue_growth": 15.5}'::jsonb,
    '{"total_expenses": 3000000, "expense_growth": 8.2}'::jsonb,
    '{"profit_margin": 25.5, "net_profit": 1275000}'::jsonb,
    '[{"metric_name": "利润率", "value": 25.5}, {"metric_name": "资产周转率", "value": 1.2}]'::jsonb,
    '[{"risk_type": "税务风险", "level": "medium", "description": "企业所得税偏高"}]'::jsonb,
    '[{"action": "优化成本结构", "priority": "high"}]'::jsonb,
    '[]'::jsonb,
    'completed',
    NOW() - INTERVAL '1 day' * (random() * 30)::int,
    NOW() - INTERVAL '1 day' * (random() * 30)::int
FROM users
LIMIT 5;
*/

-- 5. 插入 financial_anomaly_records 测试数据
/*
INSERT INTO financial_anomaly_records (
    id,
    user_id,
    tenant_id,
    report_id,
    anomaly_type,
    anomaly_category,
    severity,
    confidence,
    title,
    description,
    detected_value,
    expected_value,
    deviation,
    deviation_percentage,
    status,
    created_at
)
SELECT
    gen_random_uuid(),
    id,
    tenant_id,
    (SELECT id FROM financial_health_reports LIMIT 1),
    'revenue_drop',
    'profitability',
    CASE
        WHEN random() > 0.5 THEN 'high'
        WHEN random() > 0.2 THEN 'medium'
        ELSE 'low'
    END,
    random() * 0.3 + 0.7,  -- 置信度 0.7-1.0
    '收入异常下降',
    '检测到本季度收入较上季度下降超过20%',
    random() * 500000,
    random() * 700000,
    random() * 200000,
    random() * 30 + 10,
    'detected',
    NOW() - INTERVAL '7 days' * (random() * 10)::int
FROM users
LIMIT 5;
*/

-- 6. 插入 financial_trend_data 测试数据
/*
INSERT INTO financial_trend_data (
    id,
    user_id,
    tenant_id,
    metric_name,
    metric_category,
    metric_value,
    metric_unit,
    record_date,
    period_type,
    source,
    created_at
)
SELECT
    gen_random_uuid(),
    id,
    tenant_id,
    metric,
    'profitability',
    random() * 100,
    '%',
    CURRENT_DATE - INTERVAL '1 month' * seq,
    'monthly',
    'calculated',
    NOW() - INTERVAL '1 month' * seq
FROM users,
     unnest(ARRAY['利润率', '毛利率', '净利率', '营业利润率']) AS metric,
     generate_series(0, 11) AS seq
LIMIT 100;
*/

-- 7. 插入 financial_thresholds 测试数据
/*
INSERT INTO financial_thresholds (
    id,
    tenant_id,
    metric_name,
    metric_category,
    warning_threshold,
    critical_threshold,
    comparison_operator,
    enabled,
    created_at,
    updated_at
)
VALUES
    (gen_random_uuid(), 'default', '利润率', 'profitability', 20.0, 10.0, '<', true, NOW(), NOW()),
    (gen_random_uuid(), 'default', '毛利率', 'profitability', 30.0, 15.0, '<', true, NOW(), NOW()),
    (gen_random_uuid(), 'default', '税负率', 'tax', 25.0, 35.0, '>', true, NOW(), NOW()),
    (gen_random_uuid(), 'default', '应收账款周转率', 'operation', 5.0, 3.0, '<', true, NOW(), NOW()),
    (gen_random_uuid(), 'default', '收入增长率', 'growth', 10.0, -5.0, '<', true, NOW(), NOW());
*/

-- 8. 验证插入结果
-- SELECT COUNT(*) FROM user_financial_data;
-- SELECT COUNT(*) FROM financial_health_reports;
-- SELECT COUNT(*) FROM financial_anomaly_records;
-- SELECT COUNT(*) FROM financial_trend_data;
-- SELECT COUNT(*) FROM financial_thresholds;

-- 9. 查看测试数据样例
-- SELECT id, fiscal_year, total_revenue, total_tax_burden FROM user_financial_data LIMIT 5;
-- SELECT id, report_name, overall_health_score, health_status FROM financial_health_reports LIMIT 5;
