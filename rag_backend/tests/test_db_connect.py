#!/usr/bin/env python3
import psycopg2

print("测试 1: 直接连接 PostgreSQL")
try:
    conn = psycopg2.connect(
        host='db',
        port=5432,
        user='postgres',
        password='REDACTED_PG_PASSWORD',
        dbname='rag_db'
    )
    print("✅ 直接连接 PostgreSQL 成功")
    conn.close()
except Exception as e:
    print(f"❌ 直接连接 PostgreSQL 失败: {e}")

print("\n测试 2: 通过 PgBouncer 连接")
try:
    conn = psycopg2.connect(
        host='pgbouncer',
        port=5432,
        user='postgres',
        password='REDACTED_PG_PASSWORD',
        dbname='rag_db'
    )
    print("✅ 通过 PgBouncer 连接成功")
    conn.close()
except Exception as e:
    print(f"❌ 通过 PgBouncer 连接失败: {e}")
