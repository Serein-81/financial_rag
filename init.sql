-- PostgreSQL 初始化脚本
-- 创建 pgvector 扩展

-- 创建 pgvector 扩展（如果不存在）
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建 uuid-ossp 扩展（用于 UUID 生成）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 设置时区
SET timezone = 'Asia/Shanghai';

-- 输出初始化完成信息
SELECT 'PostgreSQL 初始化完成，已安装 pgvector 和 uuid-ossp 扩展' as message;