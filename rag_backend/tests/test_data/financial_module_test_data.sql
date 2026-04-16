-- ====================================================================
-- 财务模块测试数据 - 按依赖顺序插入
-- 生成时间: 2026-04-11
-- 执行顺序: 1.财务健康报告 -> 2.财务异常记录 -> 3.财务阈值 -> 4.财务趋势数据 -> 5.财务数据历史
-- ====================================================================

-- ====================================================================
-- 步骤1: financial_health_reports (财务健康报告)
-- 说明: 基础表，其他表可能依赖此表的ID
-- 插入3条记录
-- ====================================================================
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
    cash_flow_summary,
    financial_metrics,
    trend_indicators,
    anomaly_detections,
    risk_assessments,
    recommendations,
    revenue_data,
    expense_data,
    generated_by,
    source_data_description,
    status,
    created_at,
    completed_at,
    expires_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    '2024年Q1综合财务健康报告',
    'quarterly',
    '2024-01-01'::timestamp,
    '2024-03-31'::timestamp,
    78.5,
    'healthy',
    '{"total_revenue": 5000000, "revenue_growth": 12.5, "main_revenue_sources": ["产品销售", "服务收入"]}'::jsonb,
    '{"total_expense": 3800000, "expense_growth": 8.2, "main_expense_items": ["运营成本", "管理费用"]}'::jsonb,
    '{"gross_profit": 1200000, "net_profit": 850000, "profit_margin": 17.0}'::jsonb,
    '{"operating_cash_flow": 950000, "investing_cash_flow": -200000, "financing_cash_flow": -150000, "cash_position": 1800000}'::jsonb,
    '{"liquidity_ratio": 2.1, "current_ratio": 1.8, "debt_to_asset": 0.45, "roe": 15.2, "roa": 8.5}'::jsonb,
    '{"revenue_trend": "up", "profit_trend": "stable", "cash_flow_trend": "improving"}'::jsonb,
    '{"margin_decline": false, "cash_flow_negative": false, "debt_ratio_increase": false}'::jsonb,
    '{"high_risk": false, "medium_risk": true, "low_risk": false}'::jsonb,
    '["继续优化成本控制", "提高资产周转效率", "加强应收账款管理"]'::jsonb,
    '{"monthly": [1500000, 1600000, 1900000], "quarterly": [5000000], "yearly": null}'::jsonb,
    '{"monthly": [1200000, 1250000, 1350000], "quarterly": [3800000], "yearly": null}'::jsonb,
    'system',
    '基于2024年Q1财务数据生成，包含月度、季度收入支出数据',
    'completed',
    NOW(),
    NOW(),
    NOW() + INTERVAL '90 days'
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    'test_tenant_002',
    '2024年Q1风险预警报告',
    'quarterly',
    '2024-01-01'::timestamp,
    '2024-03-31'::timestamp,
    65.2,
    'warning',
    '{"total_revenue": 3200000, "revenue_growth": 3.2, "main_revenue_sources": ["产品销售"]}'::jsonb,
    '{"total_expense": 2900000, "expense_growth": 12.8, "main_expense_items": ["运营成本", "财务费用"]}'::jsonb,
    '{"gross_profit": 300000, "net_profit": 150000, "profit_margin": 4.7}'::jsonb,
    '{"operating_cash_flow": -150000, "investing_cash_flow": -80000, "financing_cash_flow": 300000, "cash_position": 850000}'::jsonb,
    '{"liquidity_ratio": 1.2, "current_ratio": 0.95, "debt_to_asset": 0.68, "roe": 6.8, "roa": 2.3}'::jsonb,
    '{"revenue_trend": "slow", "profit_trend": "declining", "cash_flow_trend": "worsening"}'::jsonb,
    '{"margin_decline": true, "cash_flow_negative": true, "debt_ratio_increase": true}'::jsonb,
    '{"high_risk": true, "medium_risk": false, "low_risk": false}'::jsonb,
    '["加强现金流管理", "优化库存结构", "拓展融资渠道", "控制成本费用"]'::jsonb,
    '{"monthly": [1000000, 1100000, 1100000], "quarterly": [3200000], "yearly": null}'::jsonb,
    '{"monthly": [950000, 980000, 970000], "quarterly": [2900000], "yearly": null}'::jsonb,
    'system',
    '基于2024年Q1财务数据生成，检测到多项财务风险指标',
    'completed',
    NOW(),
    NOW(),
    NOW() + INTERVAL '90 days'
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 2),
    'test_tenant_001',
    '2024年Q2优秀财务报告',
    'quarterly',
    '2024-04-01'::timestamp,
    '2024-06-30'::timestamp,
    85.6,
    'excellent',
    '{"total_revenue": 5800000, "revenue_growth": 16.0, "main_revenue_sources": ["产品销售", "服务收入", "技术授权"]}'::jsonb,
    '{"total_expense": 4000000, "expense_growth": 5.3, "main_expense_items": ["运营成本", "研发费用"]}'::jsonb,
    '{"gross_profit": 1800000, "net_profit": 1350000, "profit_margin": 23.3}'::jsonb,
    '{"operating_cash_flow": 1500000, "investing_cash_flow": -300000, "financing_cash_flow": -200000, "cash_position": 2500000}'::jsonb,
    '{"liquidity_ratio": 2.5, "current_ratio": 2.2, "debt_to_asset": 0.38, "roe": 18.5, "roa": 10.2}'::jsonb,
    '{"revenue_trend": "up", "profit_trend": "improving", "cash_flow_trend": "stable"}'::jsonb,
    '{"margin_decline": false, "cash_flow_negative": false, "debt_ratio_increase": false}'::jsonb,
    '{"high_risk": false, "medium_risk": false, "low_risk": true}'::jsonb,
    '["保持现有优势", "适度进行业务扩张", "加强风险防控", "继续研发投入"]'::jsonb,
    '{"monthly": [1800000, 1950000, 2050000], "quarterly": [5800000], "yearly": null}'::jsonb,
    '{"monthly": [1250000, 1350000, 1400000], "quarterly": [4000000], "yearly": null}'::jsonb,
    'system',
    '基于2024年Q2财务数据生成，企业财务状况优秀',
    'completed',
    NOW(),
    NOW(),
    NOW() + INTERVAL '90 days'
);

-- ====================================================================
-- 步骤2: financial_anomaly_records (财务异常记录)
-- 说明: 依赖 financial_health_reports 的 id 作为 report_id
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
-- 说明: 配置表，独立数据
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
-- 说明: 依赖 user_id，包含各类财务指标的历史趋势
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
-- 步骤5: financial_data_history (财务数据历史)
-- 说明: 记录财务数据的变更历史
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
    (SELECT id FROM financial_health_reports LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '7 days',
    '{"overall_health_score": 75.0, "health_status": "healthy"}'::jsonb,
    '{"overall_health_score": 78.5, "health_status": "healthy"}'::jsonb,
    '数据校正：根据最新财务账目调整整体评分'
),
(
    gen_random_uuid(),
    (SELECT id FROM financial_health_reports LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '5 days',
    '{"total_revenue": 4800000, "revenue_growth": 10.0}'::jsonb,
    '{"total_revenue": 5000000, "revenue_growth": 12.5}'::jsonb,
    '补充遗漏的销售数据'
),
(
    gen_random_uuid(),
    (SELECT id FROM financial_health_reports LIMIT 1 OFFSET 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '3 days',
    '{"gross_profit": 350000, "net_profit": 180000, "profit_margin": 5.5}'::jsonb,
    '{"gross_profit": 300000, "net_profit": 150000, "profit_margin": 4.7}'::jsonb,
    '成本核算调整'
),
(
    gen_random_uuid(),
    (SELECT id FROM financial_health_reports LIMIT 1 OFFSET 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '1 day',
    '{"operating_cash_flow": -100000}'::jsonb,
    '{"operating_cash_flow": -150000}'::jsonb,
    '更新银行对账单数据'
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
