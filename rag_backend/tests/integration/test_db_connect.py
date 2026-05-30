#!/usr/bin/env python3
"""数据库连通性手工诊断脚本。

密码从环境变量读取（POSTGRES_PASSWORD），不再硬编码。
运行前请先 `export POSTGRES_PASSWORD=...`，或在 Docker 容器内
（compose 已注入环境变量）执行。
"""
import os

import psycopg2

PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
if not PG_PASSWORD:
    print("⚠️ 未设置 POSTGRES_PASSWORD 环境变量，连接将以空密码尝试。")

print("测试 1: 直接连接 PostgreSQL")
try:
    conn = psycopg2.connect(
        host='db',
        port=5432,
        user='postgres',
        password=PG_PASSWORD,
        dbname='rag_db',
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
        password=PG_PASSWORD,
        dbname='rag_db',
    )
    print("✅ 通过 PgBouncer 连接成功")
    conn.close()
except Exception as e:
    print(f"❌ 通过 PgBouncer 连接失败: {e}")
