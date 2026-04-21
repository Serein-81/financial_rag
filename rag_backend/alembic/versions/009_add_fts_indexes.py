"""Add PostgreSQL Full-Text Search indexes for document_chunks

Revision ID: 009
Revises: 008
Create Date: 2026-04-21 12:00:00.000000

使用 PostgreSQL 原生全文检索 + GIN 索引
支持千万级数据的高性能检索
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加全文检索支持的迁移"""
    
    # 1. 添加 tsvector 列用于存储预处理的分词结果
    op.add_column(
        'document_chunks',
        sa.Column('fts_vector', sa.dialects.postgresql.TSVECTOR(), nullable=True)
    )
    
    # 2. 创建 GIN 索引 - 这是全文检索性能的关键
    # 使用 pg_catalog.simple 配置，适合中英文混合文本
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_chunks_fts 
        ON document_chunks 
        USING GIN (fts_vector)
    """)
    
    # 3. 创建复合索引以支持租户隔离的快速查询
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_chunks_fts_tenant 
        ON document_chunks 
        USING GIN (tenant_id, fts_vector)
    """)
    
    # 4. 创建触发器函数以自动更新 fts_vector 列
    op.execute("""
        CREATE OR REPLACE FUNCTION update_document_chunks_fts()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.fts_vector := 
                setweight(to_tsvector('pg_catalog.simple', COALESCE(NEW.content, '')), 'A') ||
                setweight(to_tsvector('pg_catalog.simple', COALESCE(NEW.heading_path, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 5. 创建触发器
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_update_document_chunks_fts ON document_chunks;
        CREATE TRIGGER trigger_update_document_chunks_fts
        BEFORE INSERT OR UPDATE OF content, heading_path ON document_chunks
        FOR EACH ROW
        EXECUTE FUNCTION update_document_chunks_fts();
    """)
    
    # 6. 为现有数据生成 fts_vector
    op.execute("""
        UPDATE document_chunks 
        SET fts_vector = 
            setweight(to_tsvector('pg_catalog.simple', COALESCE(content, '')), 'A') ||
            setweight(to_tsvector('pg_catalog.simple', COALESCE(heading_path, '')), 'B')
        WHERE fts_vector IS NULL
    """)
    
    # 7. 设置统计信息收集
    op.execute("""
        ALTER TABLE document_chunks 
        ALTER COLUMN fts_vector SET STATISTICS 500
    """)


def downgrade() -> None:
    """回滚迁移"""
    
    # 1. 删除触发器
    op.execute("DROP TRIGGER IF EXISTS trigger_update_document_chunks_fts ON document_chunks")
    
    # 2. 删除触发器函数
    op.execute("DROP FUNCTION IF EXISTS update_document_chunks_fts()")
    
    # 3. 删除索引
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_fts_tenant")
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_fts")
    
    # 4. 删除列
    op.drop_column('document_chunks', 'fts_vector')
