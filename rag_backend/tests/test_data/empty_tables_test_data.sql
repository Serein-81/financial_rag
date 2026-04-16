
-- ============================================
-- 所有空表测试数据SQL语句
-- 生成时间: 2026-04-11 21:47:59
-- ============================================


-- ============================================
-- financial_health_reports 财务健康报告
-- ============================================

-- 插入3条测试数据
INSERT INTO financial_health_reports (
    id,
    user_id,
    tenant_id,
    report_type,
    overall_score,
    liquidity_score,
    profitability_score,
    leverage_score,
    growth_score,
    risk_level,
    assessment_period_start,
    assessment_period_end,
    summary,
    detailed_analysis,
    recommendations,
    report_date,
    created_at,
    updated_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'comprehensive',
    78.5,
    82.3,
    75.6,
    68.9,
    87.2,
    'medium',
    '2024-01-01',
    '2024-03-31',
    '企业财务状况整体良好，流动性充足，盈利能力中等，杠杆率适中。',
    ' liquidity_score: 82.3\nprofitability_score: 75.6\nleverage_score: 68.9',
    '1. 继续优化成本控制\n2. 提高资产周转效率\n3. 加强应收账款管理',
    '2024-04-15',
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    'test_tenant_002',
    'comprehensive',
    65.2,
    55.8,
    72.1,
    58.3,
    74.6,
    'high',
    '2024-01-01',
    '2024-03-31',
    '企业财务状况存在一定风险，流动性指标偏低，需要关注短期偿债能力。',
    'liquidity_score: 55.8\nprofitability_score: 72.1\nleverage_score: 58.3',
    '1. 加强现金流管理\n2. 优化库存结构\n3. 拓展融资渠道',
    '2024-04-15',
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 2),
    'test_tenant_001',
    'quarterly',
    85.6,
    88.9,
    82.4,
    79.2,
    91.8,
    'low',
    '2024-04-01',
    '2024-06-30',
    '企业财务状况优秀，各项指标均表现良好，建议保持当前运营策略。',
    'liquidity_score: 88.9\nprofitability_score: 82.4\nleverage_score: 79.2',
    '1. 保持现有优势\n2. 适度进行业务扩张\n3. 加强风险防控',
    '2024-07-20',
    NOW(),
    NOW()
);

SELECT COUNT(*) AS inserted_rows FROM financial_health_reports;



-- ============================================
-- financial_anomaly_records 财务异常记录
-- ============================================

-- 插入测试数据
INSERT INTO financial_anomaly_records (
    id,
    user_id,
    tenant_id,
    report_id,
    anomaly_type,
    anomaly_category,
    severity,
    description,
    detected_value,
    expected_value,
    deviation_percentage,
    detection_date,
    acknowledged,
    acknowledged_at,
    acknowledged_by,
    created_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    (SELECT id FROM financial_health_reports LIMIT 1),
    'margin_decline',
    'profitability',
    'warning',
    '毛利率出现明显下降趋势',
    15.2,
    22.8,
    -33.3,
    '2024-03-31',
    false,
    NULL,
    NULL,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1 OFFSET 1),
    'test_tenant_002',
    (SELECT id FROM financial_health_reports LIMIT 1 OFFSET 1),
    'cash_flow_negative',
    'liquidity',
    'critical',
    '经营现金流连续两季度为负',
    -150000.00,
    50000.00,
    -400.0,
    '2024-03-31',
    true,
    NOW(),
    (SELECT id FROM users LIMIT 1),
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    (SELECT id FROM financial_health_reports LIMIT 1 OFFSET 2),
    'debt_ratio_increase',
    'leverage',
    'warning',
    '资产负债率持续上升',
    68.5,
    55.0,
    24.5,
    '2024-06-30',
    false,
    NULL,
    NULL,
    NOW()
);

SELECT COUNT(*) AS inserted_rows FROM financial_anomaly_records;



-- ============================================
-- financial_data_history 财务数据历史
-- ============================================

-- 插入测试数据
INSERT INTO financial_data_history (
    id,
    user_id,
    tenant_id,
    period_type,
    period_start,
    period_end,
    created_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'monthly',
    '2024-01-01',
    '2024-01-31',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'monthly',
    '2024-02-01',
    '2024-02-29',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'quarterly',
    '2024-01-01',
    '2024-03-31',
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'yearly',
    '2024-01-01',
    '2024-12-31',
    NOW()
);

SELECT COUNT(*) AS inserted_rows FROM financial_data_history;



-- ============================================
-- financial_thresholds 财务阈值配置
-- ============================================

-- 插入测试数据
INSERT INTO financial_thresholds (
    id,
    user_id,
    tenant_id,
    metric_name,
    warning_threshold,
    critical_threshold,
    ideal_value,
    description,
    created_at,
    updated_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'current_ratio',
    1.5,
    1.0,
    2.0,
    '流动比率阈值配置',
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'gross_margin',
    20.0,
    15.0,
    30.0,
    '毛利率阈值配置',
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'debt_to_asset_ratio',
    60.0,
    70.0,
    50.0,
    '资产负债率阈值配置',
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'roe',
    10.0,
    5.0,
    15.0,
    '净资产收益率阈值配置',
    NOW(),
    NOW()
);

SELECT COUNT(*) AS inserted_rows FROM financial_thresholds;



-- ============================================
-- financial_trend_data 财务趋势数据
-- ============================================

-- 插入测试数据
INSERT INTO financial_trend_data (
    id,
    user_id,
    tenant_id,
    metric_name,
    period_type,
    period_start,
    period_end,
    value,
    unit,
    change_rate,
    created_at
) VALUES
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'revenue',
    'quarterly',
    '2023-01-01',
    '2023-03-31',
    5000000.00,
    'CNY',
    NULL,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'revenue',
    'quarterly',
    '2023-04-01',
    '2023-06-30',
    5500000.00,
    'CNY',
    10.0,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'revenue',
    'quarterly',
    '2023-07-01',
    '2023-09-30',
    5800000.00,
    'CNY',
    5.5,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'revenue',
    'quarterly',
    '2023-10-01',
    '2023-12-31',
    6200000.00,
    'CNY',
    6.9,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'profit_margin',
    'quarterly',
    '2024-01-01',
    '2024-03-31',
    18.5,
    'percentage',
    NULL,
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_tenant_001',
    'profit_margin',
    'quarterly',
    '2024-04-01',
    '2024-06-30',
    15.2,
    'percentage',
    -17.8,
    NOW()
);

SELECT COUNT(*) AS inserted_rows FROM financial_trend_data;

