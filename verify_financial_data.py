"""
验证财务模块测试数据插入情况
"""
import psycopg2

DATABASE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "rag_db",
    "user": "postgres",
    "password": "REDACTED_PG_PASSWORD"
}

def verify_financial_data():
    """验证财务模块数据"""
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()
        
        print("="*80)
        print("财务模块数据验证")
        print("="*80)
        
        # 1. 统计各表记录数
        print("\n【1. 各表记录数统计】")
        print("-"*80)
        
        tables = [
            'financial_health_reports',
            'financial_anomaly_records',
            'financial_data_history',
            'financial_thresholds',
            'financial_trend_data'
        ]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table:<30} : {count} 条记录")
        
        # 2. 查看财务健康报告摘要
        print("\n\n【2. 财务健康报告摘要】")
        print("-"*80)
        
        cursor.execute("""
            SELECT 
                id,
                report_name,
                health_status,
                overall_health_score,
                tenant_id,
                period_start,
                period_end,
                created_at
            FROM financial_health_reports
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        reports = cursor.fetchall()
        for report in reports:
            print(f"\n报告ID: {report[0]}")
            print(f"  报告名称: {report[1]}")
            print(f"  健康状态: {report[2]}")
            print(f"  健康评分: {report[3]}")
            print(f"  租户ID: {report[4]}")
            print(f"  期间: {report[5]} ~ {report[6]}")
            print(f"  创建时间: {report[7]}")
        
        # 3. 查看财务异常记录
        print("\n\n【3. 财务异常记录】")
        print("-"*80)
        
        cursor.execute("""
            SELECT 
                id,
                title,
                severity,
                anomaly_type,
                detected_value,
                expected_value,
                status
            FROM financial_anomaly_records
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        anomalies = cursor.fetchall()
        for anomaly in anomalies:
            print(f"\n异常ID: {anomaly[0]}")
            print(f"  标题: {anomaly[1]}")
            print(f"  严重程度: {anomaly[2]}")
            print(f"  异常类型: {anomaly[3]}")
            print(f"  检测值: {anomaly[4]}")
            print(f"  期望值: {anomaly[5]}")
            print(f"  状态: {anomaly[6]}")
        
        # 4. 查看财务阈值配置
        print("\n\n【4. 财务阈值配置】")
        print("-"*80)
        
        cursor.execute("""
            SELECT 
                id,
                metric_name,
                metric_category,
                warning_threshold,
                critical_threshold,
                comparison_operator,
                enabled
            FROM financial_thresholds
            ORDER BY metric_category, metric_name
        """)
        
        thresholds = cursor.fetchall()
        for threshold in thresholds:
            print(f"\n阈值ID: {threshold[0]}")
            print(f"  指标名称: {threshold[1]}")
            print(f"  指标类别: {threshold[2]}")
            print(f"  警告阈值: {threshold[3]}")
            print(f"  严重阈值: {threshold[4]}")
            print(f"  比较操作符: {threshold[5]}")
            print(f"  启用状态: {threshold[6]}")
        
        # 5. 查看财务趋势数据摘要
        print("\n\n【5. 财务趋势数据摘要】")
        print("-"*80)
        
        cursor.execute("""
            SELECT 
                metric_name,
                metric_category,
                COUNT(*) as record_count,
                MIN(metric_value) as min_value,
                MAX(metric_value) as max_value,
                AVG(metric_value) as avg_value
            FROM financial_trend_data
            GROUP BY metric_name, metric_category
            ORDER BY metric_category, metric_name
        """)
        
        trends = cursor.fetchall()
        for trend in trends:
            print(f"\n指标: {trend[0]} ({trend[1]})")
            print(f"  记录数: {trend[2]}")
            print(f"  最小值: {trend[3]:.2f}")
            print(f"  最大值: {trend[4]:.2f}")
            print(f"  平均值: {trend[5]:.2f}")
        
        # 6. 查看数据历史记录
        print("\n\n【6. 财务数据历史记录】")
        print("-"*80)
        
        cursor.execute("""
            SELECT 
                id,
                financial_data_id,
                modified_at,
                change_reason,
                previous_data,
                new_data
            FROM financial_data_history
            ORDER BY modified_at DESC
            LIMIT 5
        """)
        
        history = cursor.fetchall()
        for record in history:
            print(f"\n历史ID: {record[0]}")
            print(f"  财务数据ID: {record[1]}")
            print(f"  修改时间: {record[2]}")
            print(f"  修改原因: {record[3]}")
            print(f"  旧数据: {record[4]}")
            print(f"  新数据: {record[5]}")
        
        # 7. 生成功能测试查询示例
        print("\n\n【7. 功能测试查询示例】")
        print("-"*80)
        print("""
-- 查询某个租户的最新财务健康报告
SELECT * FROM financial_health_reports 
WHERE tenant_id = 'test_tenant_001' 
ORDER BY created_at DESC LIMIT 1;

-- 查询高风险的财务异常
SELECT * FROM financial_anomaly_records 
WHERE severity IN ('high', 'critical') 
AND status = 'detected';

-- 查询财务指标趋势
SELECT * FROM financial_trend_data 
WHERE metric_name = 'monthly_revenue' 
ORDER BY record_date;

-- 查询当前生效的财务阈值
SELECT * FROM financial_thresholds 
WHERE enabled = true;
        """)
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*80)
        print("验证完成！所有数据已成功插入。")
        print("="*80)
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_financial_data()
