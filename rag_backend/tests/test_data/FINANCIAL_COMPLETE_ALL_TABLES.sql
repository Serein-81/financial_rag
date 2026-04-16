-- ====================================================================
-- 财务模块完整测试数据 - 全部5个表
-- 生成时间: 2026-04-11
-- 重要：完整版本，包含所有必需数据
-- ====================================================================

-- ====================================================================
-- 步骤1: financial_health_reports (财务健康报告) - 3条记录
-- 依赖: users表（已有34条记录）
-- ====================================================================

BEGIN;

-- 清空旧数据（谨慎操作！）
-- 如果已有重复数据，取消下面这行的注释
-- DELETE FROM financial_health_reports WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002');

-- 插入财务健康报告
INSERT INTO financial_health_reports (
    id, user_id, tenant_id, report_name, report_period, period_start, period_end,
    overall_health_score, health_status, revenue_summary, expense_summary, profit_summary,
    cash_flow_summary, financial_metrics, trend_indicators, anomaly_detections,
    risk_assessments, recommendations, revenue_data, expense_data, generated_by,
    source_data_description, status, created_at, completed_at, expires_at
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
    '{"total_revenue": 5000000, "revenue_growth": 12.5}'::jsonb,
    '{"total_expense": 3800000, "expense_growth": 8.2}'::jsonb,
    '{"gross_profit": 1200000, "net_profit": 850000}'::jsonb,
    '{"operating_cash_flow": 950000, "cash_position": 1800000}'::jsonb,
    '{"liquidity_ratio": 2.1, "current_ratio": 1.8}'::jsonb,
    '{"revenue_trend": "up", "profit_trend": "stable"}'::jsonb,
    '{"margin_decline": false, "cash_flow_negative": false}'::jsonb,
    '{"high_risk": false, "medium_risk": true}'::jsonb,
    '["优化成本控制", "提高资产周转效率"]'::jsonb,
    '{"monthly": [1500000, 1600000, 1900000]}'::jsonb,
    '{"monthly": [1200000, 1250000, 1350000]}'::jsonb,
    'system',
    '2024年Q1综合财务健康报告',
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
    '{"total_revenue": 3200000, "revenue_growth": 3.2}'::jsonb,
    '{"total_expense": 2900000, "expense_growth": 12.8}'::jsonb,
    '{"gross_profit": 300000, "net_profit": 150000}'::jsonb,
    '{"operating_cash_flow": -150000, "cash_position": 850000}'::jsonb,
    '{"liquidity_ratio": 1.2, "current_ratio": 0.95}'::jsonb,
    '{"revenue_trend": "slow", "profit_trend": "declining"}'::jsonb,
    '{"margin_decline": true, "cash_flow_negative": true}'::jsonb,
    '{"high_risk": true, "medium_risk": false}'::jsonb,
    '["加强现金流管理", "控制成本费用"]'::jsonb,
    '{"monthly": [1000000, 1100000, 1100000]}'::jsonb,
    '{"monthly": [950000, 980000, 970000]}'::jsonb,
    'system',
    '2024年Q1风险预警报告',
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
    '{"total_revenue": 5800000, "revenue_growth": 16.0}'::jsonb,
    '{"total_expense": 4000000, "expense_growth": 5.3}'::jsonb,
    '{"gross_profit": 1800000, "net_profit": 1350000}'::jsonb,
    '{"operating_cash_flow": 1500000, "cash_position": 2500000}'::jsonb,
    '{"liquidity_ratio": 2.5, "current_ratio": 2.2}'::jsonb,
    '{"revenue_trend": "up", "profit_trend": "improving"}'::jsonb,
    '{"margin_decline": false, "cash_flow_negative": false}'::jsonb,
    '{"high_risk": false, "medium_risk": false}'::jsonb,
    '["保持现有优势", "继续研发投入"]'::jsonb,
    '{"monthly": [1800000, 1950000, 2050000]}'::jsonb,
    '{"monthly": [1250000, 1350000, 1400000]}'::jsonb,
    'system',
    '2024年Q2优秀财务报告',
    'completed',
    NOW(),
    NOW(),
    NOW() + INTERVAL '90 days'
);

COMMIT;

-- ====================================================================
-- 步骤2: financial_anomaly_records (财务异常记录) - 4条记录
-- 依赖: users表, financial_health_reports表
-- ====================================================================

BEGIN;

-- 清空旧测试数据
DELETE FROM financial_anomaly_records WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002');

-- 插入财务异常记录
INSERT INTO financial_anomaly_records (
    id, user_id, tenant_id, report_id, anomaly_type, anomaly_category,
    severity, confidence, title, description, detected_value, expected_value,
    deviation, deviation_percentage, affected_accounts, related_transactions,
    recommended_actions, status, acknowledged, created_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_001' AND health_status = 'healthy' LIMIT 1),
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
    '["分析成本上升原因", "优化产品结构", "调整定价策略"]'::jsonb,
    'detected',
    false,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    'test_tenant_002',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_002' LIMIT 1),
    'cash_flow_negative',
    'cash_flow',
    'critical',
    0.95,
    '经营现金流为负',
    '企业经营现金流出现负数，表明日常经营资金紧张，需要及时补充流动资金',
    -150000.00,
    500000.00,
    -650000.00,
    -130.0,
    '["应收账款", "应付账款"]'::jsonb,
    '["PAY-2024-0089", "PAY-2024-0092", "PAY-2024-0098"]'::jsonb,
    '["加快应收账款回收", "延长应付账款周期", "申请短期贷款"]'::jsonb,
    'detected',
    false,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_001' AND health_status = 'excellent' LIMIT 1),
    'debt_ratio_increase',
    'solvency',
    'medium',
    0.88,
    '资产负债率上升',
    '资产负债率较上期上升5个百分点，需关注债务结构和偿债能力',
    0.55,
    0.45,
    0.10,
    22.2,
    '["短期借款", "应付账款", "预收款项"]'::jsonb,
    '["LON-2024-0045", "LON-2024-0048"]'::jsonb,
    '["优化债务结构", "控制新增负债", "提高盈利能力"]'::jsonb,
    'detected',
    true,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 2),
    'test_tenant_002',
    (SELECT id FROM financial_health_reports WHERE tenant_id = 'test_tenant_002' LIMIT 1),
    'revenue_concentration',
    'revenue_quality',
    'low',
    0.75,
    '收入来源集中度过高',
    '单一产品/客户收入占比超过70%，存在业务集中风险',
    72.5,
    50.0,
    22.5,
    45.0,
    '["产品A销售", "客户甲"]'::jsonb,
    '["INV-2024-0201", "INV-2024-0205", "INV-2024-0210"]'::jsonb,
    '["拓展新客户", "开发新产品", "降低单一依赖"]'::jsonb,
    'detected',
    false,
    NOW()
);

COMMIT;

-- ====================================================================
-- 步骤3: financial_thresholds (财务阈值配置) - 5条记录
-- 依赖: users表
-- ====================================================================

BEGIN;

-- 清空旧测试数据
DELETE FROM financial_thresholds WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002');

-- 插入财务阈值配置
INSERT INTO financial_thresholds (
    id, tenant_id, metric_name, metric_category, warning_threshold,
    critical_threshold, comparison_operator, enabled, created_by,
    updated_by, created_at, updated_at
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
    'debt_to_asset_ratio',
    'solvency',
    0.6,
    0.7,
    '<',
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
    0.0,
    -100000.00,
    '>',
    true,
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
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
    '>',
    true,
    (SELECT id FROM users LIMIT 1),
    (SELECT id FROM users LIMIT 1),
    NOW(),
    NOW()
);

COMMIT;

-- ====================================================================
-- 步骤4: financial_trend_data (财务趋势数据) - 8条记录
-- 依赖: users表
-- ====================================================================

BEGIN;

-- 清空旧测试数据
DELETE FROM financial_trend_data WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002');

-- 插入财务趋势数据
INSERT INTO financial_trend_data (
    id, user_id, tenant_id, metric_name, metric_category, metric_value,
    metric_unit, record_date, period_type, meta_data, source, created_at
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
    '{"yoy_growth": 12.8, "mom_growth": 6.67, "budget": 1500000}'::jsonb,
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
    '{"yoy_growth": 15.2, "mom_growth": 18.75, "budget": 1550000}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'quarterly_gross_margin',
    'profitability',
    12.5,
    'percent',
    '2024-01-01'::timestamp,
    'quarterly',
    '{"target": 15.0, "last_quarter": 13.2, "industry_avg": 18.5}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'quarterly_gross_margin',
    'profitability',
    18.8,
    'percent',
    '2024-04-01'::timestamp,
    'quarterly',
    '{"target": 15.0, "last_quarter": 12.5, "industry_avg": 18.5}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'current_ratio',
    'liquidity',
    1.8,
    'ratio',
    '2024-03-31'::timestamp,
    'quarterly',
    '{"warning_threshold": 1.5, "critical_threshold": 1.0}'::jsonb,
    'calculated',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    'test_tenant_002',
    'monthly_revenue',
    'revenue',
    1100000.0,
    'CNY',
    '2024-02-01'::timestamp,
    'monthly',
    '{"yoy_growth": 2.5, "mom_growth": 10.0, "budget": 1050000}'::jsonb,
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
    '{"warning_threshold": 0, "critical_threshold": -100000, "yoy_change": -125000}'::jsonb,
    'calculated',
    NOW()
);

COMMIT;

-- ====================================================================
-- 步骤5: financial_data_history (财务数据历史) - 4条记录
-- 依赖: user_financial_data表, users表
-- ====================================================================

BEGIN;

-- 清空旧测试数据
DELETE FROM financial_data_history
WHERE financial_data_id IN (
    SELECT id FROM user_financial_data WHERE user_id IN (
        SELECT id FROM users LIMIT 3
    )
);

-- 插入财务数据历史
INSERT INTO financial_data_history (
    id, financial_data_id, modified_by, modified_at,
    previous_data, new_data, change_reason
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
    (SELECT id FROM user_financial_data LIMIT 1 OFFSET 1),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '5 days',
    '{"input_tax_amount": 580000, "output_tax_amount": 720000, "net_tax_payable": 140000}'::jsonb,
    '{"input_tax_amount": 600000, "output_tax_amount": 750000, "net_tax_payable": 150000}'::jsonb,
    '补充进项发票数据，调整增值税申报数据'
),
(
    gen_random_uuid(),
    (SELECT id FROM user_financial_data LIMIT 1 OFFSET 2),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    NOW() - INTERVAL '3 days',
    '{"wages": 1200000, "benefits": 150000, "total_labor_cost": 1350000}'::jsonb,
    '{"wages": 1250000, "benefits": 160000, "total_labor_cost": 1410000}'::jsonb,
    '更新工资薪金数据，包含年终奖和社保调整'
),
(
    gen_random_uuid(),
    (SELECT id FROM user_financial_data LIMIT 1 OFFSET 3),
    (SELECT id FROM users LIMIT 1),
    NOW() - INTERVAL '1 day',
    '{"raw_materials": 800000, "labor": 600000, "overhead": 400000, "total_cost": 1800000}'::jsonb,
    '{"raw_materials": 850000, "labor": 620000, "overhead": 420000, "total_cost": 1890000}'::jsonb,
    '成本明细调整，反映原材料价格上涨和人工成本增加'
);

COMMIT;

-- ====================================================================
-- 最终验证查询
-- ====================================================================

-- 各表统计
SELECT 
    'financial_health_reports' AS table_name,
    COUNT(*) AS row_count,
    MIN(created_at) AS earliest_record,
    MAX(created_at) AS latest_record
FROM financial_health_reports
WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002')
UNION ALL
SELECT 
    'financial_anomaly_records' AS table_name,
    COUNT(*) AS row_count,
    MIN(created_at) AS earliest_record,
    MAX(created_at) AS latest_record
FROM financial_anomaly_records
WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002')
UNION ALL
SELECT 
    'financial_thresholds' AS table_name,
    COUNT(*) AS row_count,
    MIN(created_at) AS earliest_record,
    MAX(created_at) AS latest_record
FROM financial_thresholds
WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002')
UNION ALL
SELECT 
    'financial_trend_data' AS table_name,
    COUNT(*) AS row_count,
    MIN(created_at) AS earliest_record,
    MAX(created_at) AS latest_record
FROM financial_trend_data
WHERE tenant_id IN ('test_tenant_001', 'test_tenant_002')
UNION ALL
SELECT 
    'financial_data_history' AS table_name,
    COUNT(*) AS row_count,
    MIN(modified_at) AS earliest_record,
    MAX(modified_at) AS latest_record
FROM financial_data_history
ORDER BY table_name;

-- ====================================================================
-- 完成！
-- 财务模块所有5个表的数据已完整插入。
-- ====================================================================
