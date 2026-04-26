"""
向量索引自动创建脚本 - Docker 环境自动运行版本

为所有使用 pgvector embedding 的表创建向量索引
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
from typing import Dict, List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


VECTOR_TABLES_CONFIG = [
    {
        "table_name": "semantic_memories",
        "expected_dim": 1024,
        "description": "语义记忆表"
    },
    {
        "table_name": "documents",
        "expected_dim": 768,
        "description": "文档表"
    },
    {
        "table_name": "policies",
        "expected_dim": 768,
        "description": "政策表"
    },
    {
        "table_name": "chat_messages",
        "expected_dim": 1024,
        "description": "聊天消息表"
    },
    {
        "table_name": "document_chunks",
        "expected_dim": 1024,
        "description": "文档切片表",
        "note": "需要先执行 011 迁移脚本从 ARRAY(Float) 迁移到 Vector"
    }
]


def get_embedding_dimension(db, table_name: str) -> int:
    """获取指定表 embedding 列的实际维度"""
    from sqlalchemy import text
    
    result = db.execute(text(f"""
        SELECT atttypmod - 4 AS dimensions
        FROM pg_attribute
        WHERE attrelid = '{table_name}'::regclass
        AND attname = 'embedding';
    """))
    row = result.fetchone()
    return row[0] if row else 0


def check_existing_vector_index(db, table_name: str) -> List[Tuple[str, str]]:
    """检查表中是否已存在向量索引"""
    from sqlalchemy import text
    
    result = db.execute(text(f"""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = '{table_name}'
        AND indexdef LIKE '%embedding%'
    """))
    return list(result.fetchall())


def check_embedding_column_type(db, table_name: str) -> bool:
    """
    检查 embedding 列类型是否为 Vector
    
    Args:
        db: 数据库会话
        table_name: 表名
    
    Returns:
        bool: 是否为 Vector 类型
    """
    from sqlalchemy import text
    
    result = db.execute(text(f"""
        SELECT atttypid::regtype AS type_name
        FROM pg_attribute
        WHERE attrelid = '{table_name}'::regclass
        AND attname = 'embedding';
    """))
    row = result.fetchone()
    
    if not row:
        return False
    
    type_name = str(row[0]).lower()
    is_vector = 'vector' in type_name and 'array' not in type_name
    is_array = 'array' in type_name
    
    if table_name == "document_chunks" and is_array:
        logger.warning(f"  ⚠️ {table_name}: embedding 列仍为 ARRAY 类型，需要先执行迁移脚本")
        logger.warning(f"  ⚠️ 请执行 alembic 迁移或运行 document_chunks_migration.sql")
        return False
    
    return is_vector


def get_table_row_count(db, table_name: str) -> int:
    """获取表的行数"""
    from sqlalchemy import text
    
    try:
        result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        row = result.fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.warning(f"  ⚠️ 无法获取 {table_name} 行数: {e}")
        return 0


def create_vector_index_for_table(db, table_name: str, row_count: int, embedding_dim: int) -> bool:
    """
    为单个表创建向量索引
    
    Args:
        db: 数据库会话
        table_name: 表名
        row_count: 表中的数据量
        embedding_dim: 向量维度
    
    Returns:
        bool: 是否成功创建索引
    """
    from sqlalchemy import text
    
    index_name = f"{table_name}_embedding_hnsw" if row_count < 100000 else f"{table_name}_embedding_ivfflat"
    hnsw_max_dims = 2000
    
    if embedding_dim > hnsw_max_dims:
        logger.warning(f"  ⚠️ {table_name}: 向量维度 ({embedding_dim}) > {hnsw_max_dims} (pgvector 索引限制)")
        logger.warning(f"  ⚠️ {table_name}: 跳过索引创建，使用全表扫描")
        return True
    
    if row_count < 100000:
        logger.info(f"  📊 {table_name}: 数据量 {row_count} < 100k，向量维度 {embedding_dim} <= {hnsw_max_dims}，使用 HNSW 索引")
        m_value = 16
        ef_value = 64
        create_sql = f"""
        CREATE INDEX IF NOT EXISTS {table_name}_embedding_hnsw
        ON {table_name} 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = {m_value}, ef_construction = {ef_value});
        """
        index_name = f"{table_name}_embedding_hnsw"
    else:
        logger.info(f"  📊 {table_name}: 数据量 {row_count} >= 100k，使用 IVFFlat 索引")
        lists_value = max(100, row_count // 1000)
        create_sql = f"""
        CREATE INDEX IF NOT EXISTS {table_name}_embedding_ivfflat
        ON {table_name} 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = {lists_value});
        """
        index_name = f"{table_name}_embedding_ivfflat"
    
    try:
        logger.info(f"  🔧 创建索引: {index_name}")
        db.execute(text(create_sql))
        db.commit()
        logger.info(f"  ✅ {table_name}: 索引 {index_name} 创建成功!")
        
        logger.info(f"  📈 执行 ANALYZE...")
        db.execute(text(f"ANALYZE {table_name};"))
        db.commit()
        logger.info(f"  ✅ {table_name}: ANALYZE 完成")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ {table_name}: 索引创建失败: {e}")
        db.rollback()
        return False


def auto_create_vector_index():
    """
    自动为所有配置表创建向量索引
    
    根据数据量和向量维度自动选择最佳索引类型:
    - 向量维度 > 2000: 跳过索引创建（pgvector 限制）
    - 数据量 < 100k 且 维度 <= 2000: 使用 HNSW
    - 数据量 >= 100k: 使用 IVFFlat
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.exc import OperationalError
    
    if os.getenv('PGBOUNCER_ENABLED', 'false').lower() == 'true':
        db_host = os.getenv('PGBOUNCER_HOST', 'pgbouncer')
        db_port = os.getenv('PGBOUNCER_PORT', '5432')
        db_user = os.getenv('PGBOUNCER_USER') or os.getenv('POSTGRES_USER', 'postgres')
        db_pass = os.getenv('PGBOUNCER_PASSWORD') or os.getenv('POSTGRES_PASSWORD', '')
        db_name = os.getenv('PGBOUNCER_DATABASE') or os.getenv('POSTGRES_DB', 'rag_db')
    else:
        db_host = os.getenv('POSTGRES_SERVER', 'db')
        db_port = os.getenv('POSTGRES_PORT', '5432')
        db_user = os.getenv('POSTGRES_USER', 'postgres')
        db_pass = os.getenv('POSTGRES_PASSWORD', '')
        db_name = os.getenv('POSTGRES_DB', 'rag_db')
    
    database_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    logger.info("=" * 60)
    logger.info("向量索引自动创建脚本")
    logger.info(f"数据库: {db_host}:{db_port}/{db_name}")
    logger.info(f"待处理表数量: {len(VECTOR_TABLES_CONFIG)}")
    logger.info("=" * 60)
    
    max_retries = 10
    retry_delay = 3
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url, echo=False)
            Session = sessionmaker(bind=engine)
            db = Session()
            
            try:
                success_count = 0
                skip_count = 0
                fail_count = 0
                
                for idx, table_config in enumerate(VECTOR_TABLES_CONFIG, 1):
                    table_name = table_config["table_name"]
                    description = table_config["description"]
                    expected_dim = table_config["expected_dim"]
                    
                    logger.info(f"\n[{idx}/{len(VECTOR_TABLES_CONFIG)}] 处理表: {table_name} ({description})")
                    
                    try:
                        # 检查 embedding 列类型（特别是 document_chunks 需要迁移）
                        if table_name == "document_chunks":
                            if not check_embedding_column_type(db, table_name):
                                skip_count += 1
                                continue
                        
                        existing_indexes = check_existing_vector_index(db, table_name)
                        
                        if existing_indexes:
                            logger.info(f"  ✅ {table_name}: 向量索引已存在: {[idx[0] for idx in existing_indexes]}")
                            skip_count += 1
                            continue
                        
                        row_count = get_table_row_count(db, table_name)
                        embedding_dim = get_embedding_dimension(db, table_name)
                        
                        if row_count == 0:
                            logger.info(f"  ⏭️  {table_name}: 表为空 (0 行)，跳过索引创建")
                            skip_count += 1
                            continue
                        
                        logger.info(f"  📊 {table_name}: 数据量 = {row_count}, 向量维度 = {embedding_dim}")
                        
                        if create_vector_index_for_table(db, table_name, row_count, embedding_dim):
                            success_count += 1
                        else:
                            fail_count += 1
                            
                    except Exception as e:
                        logger.error(f"  ❌ {table_name}: 处理失败: {e}")
                        fail_count += 1
                        continue
                
                logger.info("\n" + "=" * 60)
                logger.info("索引创建完成!")
                logger.info(f"  ✅ 成功: {success_count}")
                logger.info(f"  ⏭️  跳过: {skip_count}")
                logger.info(f"  ❌ 失败: {fail_count}")
                logger.info("=" * 60)
                
                return fail_count == 0
                
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
