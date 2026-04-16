"""
向量索引自动创建脚本 - Docker 环境自动运行版本

为 semantic_memories 表创建向量索引
无需交互，直接执行

重要限制：
- pgvector HNSW 和 IVFFlat 索引最大维度都是 2000
- 向量维度 > 2000: 无法使用任何优化索引
- 向量维度 <= 2000: 根据数据量选择 HNSW 或 IVFFlat

在 Docker 环境中自动运行:
    docker exec -it rag_backend python -m app.migrations.auto_create_vector_index

Author: RAG Backend Team
"""

import sys
import os
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def get_embedding_dimension(db):
    """获取 embedding 列的实际维度"""
    from sqlalchemy import text
    
    result = db.execute(text("""
        SELECT atttypmod - 4 AS dimensions
        FROM pg_attribute
        WHERE attrelid = 'semantic_memories'::regclass
        AND attname = 'embedding';
    """))
    row = result.fetchone()
    return row[0] if row else 0


def auto_create_vector_index():
    """
    自动创建向量索引
    
    根据数据量和向量维度自动选择最佳索引类型:
    - 向量维度 > 2000: 跳过索引创建（pgvector 限制）
    - 数据量 < 100k 且 维度 <= 2000: 使用 HNSW
    - 数据量 >= 100k: 使用 IVFFlat
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.exc import OperationalError
    
    db_host = os.getenv('POSTGRES_SERVER', 'db')
    db_port = os.getenv('POSTGRES_PORT', '5432')
    db_user = os.getenv('POSTGRES_USER', 'rag_user')
    db_pass = os.getenv('POSTGRES_PASSWORD', 'rag_password')
    db_name = os.getenv('POSTGRES_DB', 'rag_db')
    
    database_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    logger.info("=" * 60)
    logger.info("向量索引自动创建脚本")
    logger.info(f"数据库: {db_host}:{db_port}/{db_name}")
    logger.info("=" * 60)
    
    max_retries = 10
    retry_delay = 3
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url, echo=False)
            Session = sessionmaker(bind=engine)
            db = Session()
            
            try:
                logger.info("检查 semantic_memories 表...")
                
                result = db.execute(text("SELECT COUNT(*) FROM semantic_memories"))
                row = result.fetchone()
                row_count = row[0] if row else 0
                logger.info(f"当前数据量: {row_count}")
                
                embedding_dim = get_embedding_dimension(db)
                logger.info(f"向量维度: {embedding_dim}")
                
                result = db.execute(text("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'semantic_memories'
                    AND indexdef LIKE '%embedding%'
                """))
                existing_indexes = list(result.fetchall())
                
                if existing_indexes:
                    logger.info(f"\n✅ 向量索引已存在: {[idx[0] for idx in existing_indexes]}")
                    return True
                
                hnsw_max_dims = 2000
                
                if embedding_dim > hnsw_max_dims:
                    logger.warning("=" * 60)
                    logger.warning("⚠️ 向量维度 ({}) > {} (pgvector 索引限制)".format(embedding_dim, hnsw_max_dims))
                    logger.warning("=" * 60)
                    logger.warning("pgvector 所有索引类型 (HNSW, IVFFlat) 最大支持 2000 维")
                    logger.warning("")
                    logger.warning("建议解决方案:")
                    logger.warning("  1. 在生成 embedding 时使用 <= 2000 维的模型")
                    logger.warning("     例如: text-embedding-3-small (1536维) 或 text-embedding-3-large (256/512/1024维)")
                    logger.warning("  2. 对现有向量进行 PCA 降维处理")
                    logger.warning("")
                    logger.warning("当前状态: 跳过索引创建，使用全表扫描")
                    logger.warning("=" * 60)
                    logger.info("\n✅ 迁移完成 (无索引)")
                    return True
                    
                elif row_count < 100000:
                    logger.info(f"\n数据量 < 100k，向量维度 <= {hnsw_max_dims}，使用 HNSW 索引")
                    index_type = "hnsw"
                else:
                    logger.info("\n数据量 >= 100k，使用 IVFFlat 索引")
                    index_type = "ivfflat"
                
                if index_type == "hnsw":
                    m_value = 16
                    ef_value = 64
                    create_sql = f"""
                    CREATE INDEX IF NOT EXISTS semantic_memories_embedding_hnsw
                    ON semantic_memories 
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = {m_value}, ef_construction = {ef_value});
                    """
                    index_name = "semantic_memories_embedding_hnsw"
                else:
                    lists_value = max(100, row_count // 1000)
                    create_sql = f"""
                    CREATE INDEX IF NOT EXISTS semantic_memories_embedding_ivfflat
                    ON semantic_memories 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = {lists_value});
                    """
                    index_name = "semantic_memories_embedding_ivfflat"
                
                logger.info(f"创建索引: {index_name}")
                
                db.execute(text(create_sql))
                db.commit()
                
                logger.info(f"\n✅ 索引 {index_name} 创建成功!")
                
                logger.info("\n执行 ANALYZE...")
                db.execute(text("ANALYZE semantic_memories;"))
                db.commit()
                logger.info("✅ ANALYZE 完成")
                
                logger.info("\n" + "=" * 60)
                logger.info("索引创建完成!")
                logger.info("=" * 60)
                
                return True
                
            finally:
                db.close()
                engine.dispose()
                
        except OperationalError as e:
            logger.warning(f"数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                logger.error("达到最大重试次数，退出")
                raise
        except Exception as e:
            logger.error(f"❌ 错误: {e}")
            raise
    
    return False


if __name__ == "__main__":
    success = auto_create_vector_index()
    sys.exit(0 if success else 1)
