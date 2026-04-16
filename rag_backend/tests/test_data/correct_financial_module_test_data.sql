-- ====================================================================
-- 财务模块测试数据 - 修正版（按正确依赖顺序）
-- 生成时间: 2026-04-11
-- 修正内容: financial_data_history 引用 user_financial_data.id
-- ====================================================================

-- ====================================================================
-- 步骤1: financial_health_reports (财务健康报告) - 已有数据，跳过
-- 说明: 基础表，其他表可能依赖此表的ID
-- ====================================================================
-- 注意: 此表已有3条数据，跳过插入

-- ====================================================================
-- 步骤2: financial_anomaly_records (财务异常记录)
-- 说明: 依赖 users.id 和 financial_health_reports.id
-- 插入4条记录
-- ====================================================================
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
    affected_accounts,
    related_transactions,
    recommended_actions,
    status,
    acknowledged,
    acknowledged_by,
    acknowledged_at,
    created_at,
    resolved_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_002',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_002' LIMIT 1),
    'margin_decline',
    'profitability',
    'high',
    0.92,
    '毛利率异常下降',
    '检测到毛利率较上期下降超过15%，需要重点关注成本控制和定价策略',
    4.7,
    12.0,
    -7.3,
    -60.8,
    '["主营业务成本", "产品定价"]'::jsonb,
    '["INV-2024-0156", "INV-2024-0189", "INV-2024-0223"]'::jsonb,
    '["分析成本上升原因", "优化产品结构", "调整定价策略", "加强成本控制"]'::jsonb,
    'detected',
    false,
    NULL,
    NULL,
    NOW(),
    NULL
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_002',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_002' LIMIT 1),
    'cash_flow_negative',
    'liquidity',
    'critical',
    0.95,
    '经营现金流为负',
    '企业经营现金流出现负数，可能面临流动性风险',
    -150000.0,
    800000.0,
    -950000.0,
    -118.75,
    '["应收账款", "存货", "应付账款"]'::jsonb,
    '["PAY-2024-0089", "PAY-2024-0092"]'::jsonb,
    '["加速应收账款回收", "优化存货管理", "拓展融资渠道", "控制非必要支出"]'::jsonb,
    'detected',
    false,
    NULL,
    NULL,
    NOW(),
    NULL
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_002',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_002' LIMIT 1),
    'debt_ratio_increase',
    'leverage',
    'medium',
    0.88,
    '资产负债率上升',
    '资产负债率较上期上升超过10个百分点，需要关注债务结构',
    0.68,
    0.55,
    0.13,
    23.6,
    '["短期借款", "长期借款", "应付账款"]'::jsonb,
    '["LON-2024-0023", "LON-2024-0028"]'::jsonb,
    '["优化债务结构", "控制新增负债", "提高资产周转效率"]'::jsonb,
    'detected',
    false,
    NULL,
    NULL,
    NOW(),
    NULL
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_001' ORDER BY created_at DESC LIMIT 1),
    'revenue_concentration',
    'business',
    'low',
    0.75,
    '收入来源集中度过高',
    '单一产品收入占比超过70%，存在业务集中风险',
    75.0,
    50.0,
    25.0,
    50.0,
    '["产品A销售收入"]'::jsonb,
    '["INV-2024-0101", "INV-2024-0102"]'::jsonb,
    '["拓展产品线", "开发新客户群体", "增加服务收入占比"]'::jsonb,
    'detected',
    false,
    NULL,
    NULL,
    NOW(),
    NULL
);

-- ====================================================================
-- 步骤3: financial_thresholds (财务阈值配置)
-- 说明: 依赖 users.id，独立数据
-- 插入5条记录
-- ====================================================================
INSERT INTO financial_thresholds (
    id,
    tenant_id,
    metric_name,
    metric_category,
    warning_threshold,
    critical_threshold,
    comparison_operator,
    enabled,
    created_by,
    updated_by,
    created_at,
    updated_at
) VALUES
(
    gen_random_uuid(),
    'test_tenant_001',
    'current_ratio',
    'liquidity',
    1.5,
    1.0,
    '>',
    true,
    (SELECT id FROM users LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'test_tenant_001',
    'gross_profit_margin',
    'profitability',
    15.0,
    10.0,
    '<',
    true,
    (SELECT id FROM users LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'test_tenant_001',
    'debt_to_asset_ratio',
    'leverage',
    0.6,
    0.75,
    '>',
    true,
    (SELECT id FROM users LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'test_tenant_002',
    'operating_cash_flow',
    'cash_flow',
    500000.0,
    0.0,
    '<',
    true,
    (SELECT id FROM users LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'test_tenant_001',
    'roe',
    'profitability',
    12.0,
    8.0,
    '<',
    true,
    (SELECT id FROM users LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW(),
    NOW()
);

-- ====================================================================
-- 步骤4: financial_trend_data (财务趋势数据)
-- 说明: 依赖 users.id，包含各类财务指标的历史趋势
-- 插入8条记录
-- ====================================================================
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
    meta_data,
    source,
    created_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'monthly_revenue',
    'revenue',
    1500000.0,
    'CNY',
    '2024-01-01'::timestamp,
    'monthly',
    '{"yoy_growth": 10.5, "mom_growth": null, "budget": 1450000}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'monthly_revenue',
    'revenue',
    1600000.0,
    'CNY',
    '2024-02-01'::timestamp,
    'monthly',
    '{"yoy_growth": 12.3, "mom_growth": 6.7, "budget": 1500000}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'monthly_revenue',
    'revenue',
    1900000.0,
    'CNY',
    '2024-03-01'::timestamp,
    'monthly',
    '{"yoy_growth": 15.8, "mom_growth": 18.75, "budget": 1550000}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'gross_profit_margin',
    'profitability',
    24.0,
    '%',
    '2024-01-01'::timestamp,
    'quarterly',
    '{"industry_avg": 22.5, "competitor_avg": 23.8}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'gross_profit_margin',
    'profitability',
    17.0,
    '%',
    '2024-01-01'::timestamp,
    'quarterly',
    '{"industry_avg": 22.5, "competitor_avg": 23.8}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'current_ratio',
    'liquidity',
    2.1,
    'ratio',
    '2024-03-31'::timestamp,
    'quarterly',
    '{"industry_avg": 1.8, "warning_threshold": 1.5}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    'test_tenant_002',
    'monthly_revenue',
    'revenue',
    1000000.0,
    'CNY',
    '2024-01-01'::timestamp,
    'monthly',
    '{"yoy_growth": 2.5, "mom_growth": null, "budget": 1050000}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    'test_tenant_002',
    'operating_cash_flow',
    'cash_flow',
    -150000.0,
    'CNY',
    '2024-03-31'::timestamp,
    'quarterly',
    '{"warning_threshold": 500000, "critical_threshold": 0}'::jsonb,
    'calculated',
    NOW()
);

-- ====================================================================
-- 步骤5: financial_data_history (财务数据历史) - 修正
-- 说明: 依赖 users.id 和 user_financial_data.id（不是financial_health_reports.id）
-- 插入4条记录
-- ====================================================================
INSERT INTO financial_data_history (
    id,
    financial_data_id,
    modified_by,
    modified_at,
    previous_data,
    new_data,
    change_reason
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM user_financial_data LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '7 days',
    '{"total_revenue": 4800000, "total_expenses": 3800000, "profit_margin": 20.8}'::jsonb,
    '{"total_revenue": 5000000, "total_expenses": 4000000, "profit_margin": 20.0}'::jsonb,
    '数据校正：根据最新财务账目调整整体收入和支出数据'
),
(
    gen_random_uuid(),
    (SELECT id FROM user_financial_data LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '5 days',
    '{"input_tax": 580000, "output_tax": 650000}'::jsonb,
    '{"input_tax": 620000, "output_tax": 650000}'::jsonb,
    '补充遗漏的进项发票数据'
),
(
    gen_random_uuid(),
    (SELECT id FROM user_financial_data LIMIT 1 OFFSET 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '3 days',
    '{"total_payroll": 1500000, "special_deductions": 500000}'::jsonb,
    '{"total_payroll": 1650000, "special_deductions": 550000}'::jsonb,
    '更新工资薪金数据'
),
(
    gen_random_uuid(),
    (SELECT id FROM user_financial_data LIMIT 1 OFFSET 2),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '1 day',
    '{"cost_breakdown": {"原材料": 1500000, "人工成本": 800000, "制造费用": 500000}}'::jsonb,
    '{"cost_breakdown": {"原材料": 1550000, "人工成本": 850000, "制造费用": 550000}}'::jsonb,
    '成本明细调整'
);

-- ====================================================================
-- 验证查询
-- ====================================================================
SELECT 
    'financial_health_reports' AS table_name,
    COUNT(*) AS row_count,
    MIN(created_at) AS earliest_record,
    MAX(created_at) AS latest_record
FROM financial_health_reports
UNION ALL
SELECT 
    'financial_anomaly_records',
    COUNT(*),
    MIN(created_at),
    MAX(created_at)
FROM financial_anomaly_records
UNION ALL
SELECT 
    'financial_data_history',
    COUNT(*),
    MIN(modified_at),
    MAX(modified_at)
FROM financial_data_history
UNION ALL
SELECT 
    'financial_thresholds',
    COUNT(*),
    MIN(created_at),
    MAX(created_at)
FROM financial_thresholds
UNION ALL
SELECT 
    'financial_trend_data',
    COUNT(*),
    MIN(record_date),
    MAX(record_date)
FROM financial_trend_data
ORDER BY table_name;

-- ====================================================================
-- 执行完成提示
-- ====================================================================
