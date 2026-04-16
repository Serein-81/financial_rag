"""
查询所有财务相关空表的实际结构 - 完整版本
"""
import psycopg2

DATABASE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "rag_db",
    "user": "postgres",
    "password": "REDACTED_PG_PASSWORD"
}

def get_table_columns(cursor, table_name):
    """获取表的列信息"""
    cursor.execute("""
        SELECT 
            column_name, 
            data_type, 
            is_nullable, 
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_name = %s
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table_name,))
    return cursor.fetchall()

def generate_insert_sql(table_name, columns):
    """生成INSERT语句骨架"""
    col_names = [col[0] for col in columns]
    
    print(f"\n{'='*80}")
    print(f"INSERT 语句骨架 - {table_name}")
    print(f"{'='*80}")
    
    print(f"\nINSERT INTO {table_name} (")
    for i, col in enumerate(col_names):
        if i < len(col_names) - 1:
            print(f"    {col},")
        else:
            print(f"    {col}")
    print(") VALUES")
    print("(")
    
    for i, col in enumerate(columns):
        col_name = col[0]
        data_type = col[1]
        
        # 根据数据类型提供示例值
        if 'uuid' in data_type:
            if col_name in ['id', 'user_id', 'modified_by']:
                example = "gen_random_uuid()"
            elif 'report_id' in col_name or 'financial_data_id' in col_name:
                example = "(SELECT id FROM financial_health_reports LIMIT 1)"
            else:
                example = "gen_random_uuid()"
        elif 'timestamp' in data_type or 'date' in data_type:
            if 'start' in col_name or 'end' in col_name:
                example = "'2024-01-01'::timestamp"
            elif 'at' in col_name:
                example = "NOW()"
            else:
                example = "NOW()"
        elif 'integer' in data_type or 'bigint' in data_type or 'smallint' in data_type:
            example = "0"
        elif 'numeric' in data_type or 'double' in data_type or 'real' in data_type:
            example = "0.0"
        elif 'boolean' in data_type:
            example = "false"
        elif 'text' in data_type or 'character' in data_type:
            example = "'example_value'"
        elif 'json' in data_type or 'jsonb' in data_type:
            example = "'{}'::jsonb"
        elif 'ARRAY' in data_type:
            example = "'{}'"
        else:
            example = "NULL"
        
        if i < len(columns) - 1:
            print(f"    {example:>40},  -- {col_name}")
        else:
            print(f"    {example:>40}   -- {col_name}")
    print(");")

def main():
    """主函数"""
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()
        
        # 查询所有财务相关的空表
        tables = [
            'financial_health_reports',
            'financial_anomaly_records',
            'financial_data_history',
            'financial_thresholds',
            'financial_trend_data'
        ]
        
        print(f"{'='*80}")
        print("财务模块表结构分析")
        print(f"{'='*80}")
        
        for table_name in tables:
            print(f"\n\n{'#'*80}")
            print(f"## 表: {table_name}")
            print(f"{'#'*80}")
            
            columns = get_table_columns(cursor, table_name)
            
            print(f"\n总列数: {len(columns)}")
            print("\n列信息:")
            print(f"{'-'*80}")
            
            for col in columns:
                col_name = col[0]
                data_type = col[1]
                
                # 处理数据类型长度
                if col[4]:  # character_maximum_length
                    data_type = f"{data_type}({col[4]})"
                elif col[5] and col[6] is not None:  # numeric_precision and numeric_scale
                    data_type = f"{data_type}({col[5]},{col[6]})"
                
                nullable = "YES" if col[2] == 'YES' else "NO"
                default = str(col[3])[:20] if col[3] else ""
                
                print(f"  {col_name:<30} | {data_type:<25} | Nullable: {nullable:<3} | Default: {default}")
            
            # 生成INSERT语句骨架
            generate_insert_sql(table_name, columns)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
