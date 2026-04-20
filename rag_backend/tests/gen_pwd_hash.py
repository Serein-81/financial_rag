#!/usr/bin/env python3
import hashlib

# PostgreSQL 密码
password = "REDACTED_PG_PASSWORD"
username = "postgres"

# 生成 md5 哈希 (格式: md5 + md5(password + username))
md5_input = password + username
md5_hash = hashlib.md5(md5_input.encode()).hexdigest()
md5_pgbouncer = "md5" + md5_hash

print(f"PostgreSQL 密码: {password}")
print(f"用户名: {username}")
print(f"PgBouncer md5 哈希: {md5_pgbouncer}")

# 写入文件
with open("/tmp/pgbouncer_userlist.txt", "w") as f:
    f.write(f'"postgres" "{md5_pgbouncer}"')
print(f"\n已写入: /tmp/pgbouncer_userlist.txt")
print(f'内容: "postgres" "{md5_pgbouncer}"')
