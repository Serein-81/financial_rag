"""
为所有空表生成SQL测试数据脚本
主要关注财务健康相关的5个表
"""
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import uuid
import random

DATABASE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "rag_db",
    "user": "postgres",
    "password": "REDACTED_PG_PASSWORD"
}

def get_database_connection():
    """获取数据库连接"""
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def get_table_columns(cursor, table_name):
    """获取表的列信息"""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cursor.fetchall()

def get_primary_key(cursor, table_name):
    """获取表的主键"""
    cursor.execute("""
        SELECT kcu.column_name
        FROM information_schema.key_column_usage kcu
        JOIN information_schema.table_constraints tc
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND kcu.table_name = %s
            AND kcu.table_schema = 'public'
    """, (table_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_foreign_keys(cursor, table_name):
    """获取表的外键"""
    cursor.execute("""
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = %s
            AND tc.table_schema = 'public'
    """, (table_name,))
    return cursor.fetchall()

def generate_uuid():
    """生成UUID"""
    return str(uuid.uuid4())

def generate_sql_for_financial_health_reports(cursor):
    """为 financial_health_reports 表生成SQL"""
    print("\n" + "="*80)
    print("1. financial_health_reports 表")
    print("="*80)
    
    columns = get_table_columns(cursor, 'financial_health_reports')
    
    print("\n表结构:")
    for col in columns:
        print(f"  {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
    
    print("\n\n建议的SQL测试数据:")
    
    sql = """
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
    ' liquidity_score: 82.3\\nprofitability_score: 75.6\\nleverage_score: 68.9',
    '1. 继续优化成本控制\\n2. 提高资产周转效率\\n3. 加强应收账款管理',
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
    'liquidity_score: 55.8\\nprofitability_score: 72.1\\nleverage_score: 58.3',
    '1. 加强现金流管理\\n2. 优化库存结构\\n3. 拓展融资渠道',
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
    'liquidity_score: 88.9\\nprofitability_score: 82.4\\nleverage_score: 79.2',
    '1. 保持现有优势\\n2. 适度进行业务扩张\\n3. 加强风险防控',
    '2024-07-20',
    NOW(),
    NOW()
);

SELECT COUNT(*) AS inserted_rows FROM financial_health_reports;
"""
    print(sql)
    return sql

def generate_sql_for_financial_anomaly_records(cursor):
    """为 financial_anomaly_records 表生成SQL"""
    print("\n" + "="*80)
    print("2. financial_anomaly_records 表")
    print("="*80)
    
    columns = get_table_columns(cursor, 'financial_anomaly_records')
    
    print("\n表结构:")
    for col in columns:
        print(f"  {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
    
    print("\n\n建议的SQL测试数据:")
    
    sql = """
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
"""
    print(sql)
    return sql

def generate_sql_for_financial_data_history(cursor):
    """为 financial_data_history 表生成SQL"""
    print("\n" + "="*80)
    print("3. financial_data_history 表")
    print("="*80)
    
    columns = get_table_columns(cursor, 'financial_data_history')
    
    print("\n表结构:")
    for col in columns:
        print(f"  {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
    
    print("\n\n建议的SQL测试数据:")
    
    sql = """
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
"""
    print(sql)
    return sql

def generate_sql_for_financial_thresholds(cursor):
    """为 financial_thresholds 表生成SQL"""
    print("\n" + "="*80)
    print("4. financial_thresholds 表")
    print("="*80)
    
    columns = get_table_columns(cursor, 'financial_thresholds')
    
    print("\n表结构:")
    for col in columns:
        print(f"  {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
    
    print("\n\n建议的SQL测试数据:")
    
    sql = """
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
"""
    print(sql)
    return sql

def generate_sql_for_financial_trend_data(cursor):
    """为 financial_trend_data 表生成SQL"""
    print("\n" + "="*80)
    print("5. financial_trend_data 表")
    print("="*80)
    
    columns = get_table_columns(cursor, 'financial_trend_data')
    
    print("\n表结构:")
    for col in columns:
        print(f"  {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
    
    print("\n\n建议的SQL测试数据:")
    
    sql = """
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
"""
    print(sql)
    return sql

def generate_sql_for_other_tables(cursor):
    """为其他空表生成SQL（简化版本）"""
    
    tables = [
        'enterprise_policy_matches',
        'multi_agent_intent_analyses',
        'multi_agent_reflection_records',
        'multi_agent_report_access_logs',
        'multi_agent_report_versions',
        'multi_agent_reports',
        'multi_agent_sessions',
        'multi_agent_specialist_results',
        'policy_relations',
        'review_request_actions',
        'review_request_comments',
        'review_requests',
        'task_execution_logs',
        'task_notifications',
        'tax_report_documents',
        'update_history'
    ]
    
    print("\n\n")
    print("="*80)
    print("其他空表的SQL测试数据（需要时可选择性执行）")
    print("="*80)
    
    for i, table_name in enumerate(tables, start=6):
        print(f"\n{'-'*80}")
        print(f"{i}. {table_name} 表")
        print(f"{'-'*80}")
        
        columns = get_table_columns(cursor, table_name)
        primary_key = get_primary_key(cursor, table_name)
        foreign_keys = get_foreign_keys(cursor, table_name)
        
        print(f"主键: {primary_key}")
        print(f"外键数量: {len(foreign_keys)}")
        print(f"列数: {len(columns)}")
        
        # 生成简单的INSERT语句骨架
        col_names = [col[0] for col in columns[:5]]  # 只显示前5列
        print(f"前5列: {', '.join(col_names)}")

def main():
    """主函数"""
    print("正在连接数据库...")
    
    conn = get_database_connection()
    if not conn:
        print("无法连接到数据库，请检查配置")
        return
    
    try:
        cursor = conn.cursor()
        
        # 1. 财务健康相关的5个核心表
        sql1 = generate_sql_for_financial_health_reports(cursor)
        sql2 = generate_sql_for_financial_anomaly_records(cursor)
        sql3 = generate_sql_for_financial_data_history(cursor)
        sql4 = generate_sql_for_financial_thresholds(cursor)
        sql5 = generate_sql_for_financial_trend_data(cursor)
        
        # 2. 其他空表
        generate_sql_for_other_tables(cursor)
        
        # 保存所有SQL到文件
        all_sql = f"""
-- ============================================
-- 所有空表测试数据SQL语句
-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- ============================================

{sql1}

{sql2}

{sql3}

{sql4}

{sql5}
"""
        
        # 写入文件
        with open('empty_tables_test_data.sql', 'w', encoding='utf-8') as f:
            f.write(all_sql)
        
        print("\n\n" + "="*80)
        print("SQL文件已生成: empty_tables_test_data.sql")
        print("="*80)
        print("\n执行顺序建议:")
        print("1. 先执行财务健康相关的5个表（已在上方详细展示）")
        print("2. 其他表可根据实际需要选择性执行")
        print("\n注意事项:")
        print("- 执行前请确保 users 表有数据（用于生成外键引用）")
        print("- 部分SQL使用了子查询获取用户ID")
        print("- 建议在测试环境执行，生产环境请谨慎")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
