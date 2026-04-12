"""
向量索引迁移脚本 - Docker 环境专用版本

为 semantic_memories 表添加优化的向量索引
支持 HNSW 和 IVFFlat 索引类型

在 Docker 环境中运行:
    docker exec -it rag_backend python -m app.migrations.add_vector_indexes_docker

或使用 docker-compose:
    docker-compose exec backend python -m app.migrations.add_vector_indexes_docker

Author: RAG Backend Team
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def create_vector_indexes():
    """
    创建向量索引（Docker 环境版本）

    索引说明:
    - HNSW: 适合小数据量(~100k)，查询速度快，建构慢，内存占用高
    - IVFFlat: 适合大数据量(100k+)，查询速度中等，建构快，内存占用低

    选择建议:
    - 数据量 < 10万: 使用 HNSW
    - 数据量 10-100万: 使用 IVFFlat 或 HNSW
    - 数据量 > 100万: 使用 IVFFlat
    """
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    
    database_url = os.getenv(
        "DATABASE_URL",
        f"postgresql://{os.getenv('POSTGRES_USER', 'rag_user')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'rag_password')}@"
        f"{os.getenv('POSTGRES_SERVER', 'db')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'rag_db')}"
    )
    
    logger.info("=" * 60)
    logger.info("向量索引迁移脚本 (Docker 环境)")
    logger.info("=" * 60)
    logger.info(f"数据库: {os.getenv('POSTGRES_SERVER', 'db')}:{os.getenv('POSTGRES_PORT', '5432')}")
    logger.info(f"数据库名: {os.getenv('POSTGRES_DB', 'rag_db')}")
    
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        result = db.execute(text("SELECT COUNT(*) FROM semantic_memories"))
        row = result.fetchone()
        row_count = row[0] if row else 0
        logger.info(f"\n当前数据量: {row_count}")
        
        result = db.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'semantic_memories'
        """))
        existing_indexes = list(result.fetchall())
        
        logger.info(f"\n现有索引: {len(existing_indexes)} 个")
        for idx_name, idx_def in existing_indexes:
            logger.info(f"  - {idx_name}")
        
        has_vector_index = any('vector' in str(idx_def).lower() for _, idx_def in existing_indexes)
        
        if has_vector_index:
            logger.info("\n✅ 向量索引已存在，跳过创建")
            return
        
        logger.info("\n" + "=" * 60)
        logger.info("索引类型选择指南:")
        logger.info("=" * 60)
        logger.info("1. HNSW 索引:")
        logger.info("   - 查询速度最快")
        logger.info("   - 适合 < 100k 数据量")
        logger.info("   - 内存占用较高")
        logger.info("\n2. IVFFlat 索引:")
        logger.info("   - 查询速度中等")
        logger.info("   - 适合 > 100k 数据量")
        logger.info("   - 内存占用较低")
        logger.info("\n3. 跳过 (暂不创建索引)")
        
        index_type = input("\n请选择索引类型 (1/2/3，默认为 1): ").strip() or "1"
        
        if index_type == "3":
            logger.info("\n跳过索引创建")
            return
        
        embedding_dim = 1024
        dim_input = input(f"\n请输入向量维度 (默认为 {embedding_dim}): ").strip()
        if dim_input and dim_input.isdigit():
            embedding_dim = int(dim_input)
        
        if index_type == "1":
            m_param = input("HNSW m 参数 (默认 16，更高=更快但更占内存): ").strip()
            m_value = int(m_param) if m_param and m_param.isdigit() else 16
            
            ef_construction = input("HNSW ef_construction 参数 (默认 64): ").strip()
            ef_value = int(ef_construction) if ef_construction and ef_construction.isdigit() else 64
            
            logger.info(f"\n正在创建 HNSW 索引 (m={m_value}, ef_construction={ef_value})...")
            
            create_sql = f"""
            CREATE INDEX IF NOT EXISTS semantic_memories_embedding_hnsw
            ON semantic_memories 
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = {m_value}, ef_construction = {ef_value});
            """
            
        else:
            lists_param = input("IVFFlat lists 参数 (默认 100): ").strip()
            lists_value = int(lists_param) if lists_param and lists_param.isdigit() else 100
            
            logger.info(f"\n正在创建 IVFFlat 索引 (lists={lists_value})...")
            
            create_sql = f"""
            CREATE INDEX IF NOT EXISTS semantic_memories_embedding_ivfflat
            ON semantic_memories 
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {lists_value});
            """
        
        logger.info("\n执行 SQL:")
        logger.info(create_sql)
        
        confirm = input("\n确认执行? (y/N): ").strip().lower()
        
        if confirm == 'y':
            db.execute(text(create_sql))
            db.commit()
            logger.info("\n✅ 索引创建成功!")
            logger.info("\n创建完成后，建议执行 ANALYZE:")
            logger.info("    ANALYZE semantic_memories;")
        else:
            logger.info("\n已取消")
            
    except Exception as e:
        logger.error(f"❌ 错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_vector_indexes()
