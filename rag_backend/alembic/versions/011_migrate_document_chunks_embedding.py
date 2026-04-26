"""Migrate document_chunks embedding from ARRAY(Float) to Vector

Revision ID: 011
Revises: 010
Create Date: 2026-04-23 12:00:00.000000

将 document_chunks.embedding 从 ARRAY(Float) 迁移到 Vector 类型
支持 pgvector 的 HNSW/IVFFlat 索引优化
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    迁移 document_chunks.embedding 从 ARRAY(Float) 到 Vector(1024)
    
    迁移步骤：
    1. 添加新的 Vector 类型列
    2. 迁移数据（类型转换）
    3. 创建 HNSW 向量索引
    4. 删除旧列
    5. 重命名新列
    """
    
    # 1. 添加新的 Vector 类型列
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS embedding_vector vector(1024)
    """)
    
    # 2. 迁移现有数据
    # 从 ARRAY(Float) 转换到 Vector
    op.execute("""
        UPDATE document_chunks 
        SET embedding_vector = embedding::vector
        WHERE embedding IS NOT NULL
    """)
    
    # 3. 检查表数据量，决定使用哪种索引
    # 这里先创建 HNSW 索引（适合 < 100k 数据量）
    # 大数据量可以使用 IVFFlat
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw 
        ON document_chunks 
        USING hnsw (embedding_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    
    # 4. 设置统计信息
    op.execute("""
        ALTER TABLE document_chunks 
        ALTER COLUMN embedding_vector SET STATISTICS 500
    """)
    
    # 5. 执行 ANALYZE 优化查询计划
    op.execute("ANALYZE document_chunks")
    
    # 6. 删除旧的 ARRAY(Float) 列
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    
    # 7. 重命名新列
    op.execute("ALTER TABLE document_chunks RENAME COLUMN embedding_vector TO embedding")
    
    # 8. 更新模型注释（可选，用于文档）
    # 注意：实际的模型文件需要手动更新


def downgrade() -> None:
    """
    回滚迁移：将 embedding 从 Vector 恢复到 ARRAY(Float)
    
    注意：回滚会导致精度损失，不建议在生产环境使用
    """
    
    # 1. 添加临时 ARRAY(Float) 列
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS embedding_old float[]
    """)
    
    # 2. 恢复数据（注意：精度可能降低）
    op.execute("""
        UPDATE document_chunks 
        SET embedding_old = ARRAY(SELECT unnest(embedding::float[]))
        WHERE embedding IS NOT NULL
    """)
    
    # 3. 删除 Vector 列
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    
    # 4. 重命名回旧列
    op.execute("ALTER TABLE document_chunks RENAME COLUMN embedding_old TO embedding")
    
    # 5. 删除索引
    op.execute("DROP INDEX IF EXISTS document_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS document_chunks_embedding_ivfflat")
