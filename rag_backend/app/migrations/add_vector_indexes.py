"""
向量索引迁移脚本

为 semantic_memories 表添加优化的向量索引
支持 HNSW 和 IVFFlat 索引类型

使用方法:
    python -m app.migrations.add_vector_indexes

Author: RAG Backend Team
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def create_vector_indexes():
    """
    创建向量索引（同步版本）

    索引说明:
    - HNSW: 适合小数据量(~100k)，查询速度快，建构慢，内存占用高
    - IVFFlat: 适合大数据量(100k+)，查询速度中等，建构快，内存占用低

    选择建议:
    - 数据量 < 10万: 使用 HNSW
    - 数据量 10-100万: 使用 IVFFlat 或 HNSW
    - 数据量 > 100万: 使用 IVFFlat
    """

    from app.db.session import SessionLocal
    from sqlalchemy import text

    print("=" * 60)
    print("向量索引迁移脚本")
    print("=" * 60)

    db = SessionLocal()
    try:
        result = db.execute(text("SELECT COUNT(*) FROM semantic_memories"))
        row = result.fetchone()
        row_count = row[0] if row else 0
        print(f"\n当前数据量: {row_count}")

        result = db.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'semantic_memories'
            AND indexname LIKE '%embedding%'
        """))
        existing_indexes = result.fetchall()

        print("\n现有索引:")
        if existing_indexes:
            for idx in existing_indexes:
                print(f"  - {idx[0]}")
        else:
            print("  - 无")

        print("\n" + "-" * 60)
        print("索引选项:")
        print("-" * 60)
        print("1. HNSW 索引 (推荐小数据量 < 100k)")
        print("   - 查询速度最快")
        print("   - 构建时间较长")
        print("   - 内存占用较高")
        print()
        print("2. IVFFlat 索引 (推荐大数据量 >= 100k)")
        print("   - 查询速度中等")
        print("   - 构建速度快")
        print("   - 内存占用较低")
        print()
        print("3. 两者都创建")
        print("4. 仅创建元数据过滤索引")
        print("-" * 60)

        choice = input("\n请选择 (1-4) [默认: 1]: ").strip() or "1"

        if choice == "1":
            create_hnsw_index(db)
        elif choice == "2":
            create_ivfflat_index(db, row_count)
        elif choice == "3":
            create_hnsw_index(db)
            create_ivfflat_index(db, row_count)
        elif choice == "4":
            create_metadata_index(db)
        else:
            print("无效选择，使用默认 HNSW 索引")
            create_hnsw_index(db)

        print("\n" + "=" * 60)
        print("迁移完成!")
        print("=" * 60)

        show_index_stats(db)

    except (ValueError, KeyError) as e:
        print(f"\n❌ 迁移数据错误: {e}")
        db.rollback()
    except (OSError, IOError) as e:
        print(f"\n❌ 迁移IO错误: {e}")
        db.rollback()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_hnsw_index(db):
    """
    创建 HNSW 索引

    HNSW 参数说明:
    - m: 每个元素的最大连接数 (推荐: 8-64, 默认: 16)
      - 值越大精度越高，但内存占用和构建时间也越高
    - ef_construction: 构建时的探索因子 (推荐: 64-400, 默认: 64)
      - 值越大构建越慢，但精度越高
    """
    print("\n📦 创建 HNSW 索引...")

    m = 16
    ef_construction = 64

    custom = input("使用自定义参数? (y/N): ").strip().lower()
    if custom == 'y':
        try:
            m_input = input(f"  m (连接数, 默认 16): ").strip()
            if m_input:
                m = int(m_input)
            ef_input = input(f"  ef_construction (探索因子, 默认 64): ").strip()
            if ef_input:
                ef_construction = int(ef_input)
        except ValueError:
            print("  使用默认参数")
            m = 16
            ef_construction = 64

    print(f"  参数: m={m}, ef_construction={ef_construction}")

    try:
        sql = f"""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_semantic_memories_embedding_hnsw
        ON semantic_memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = {m}, ef_construction = {ef_construction});
        """
        db.execute(text(sql))
        db.commit()
        print("  ✅ HNSW 索引创建成功")

        sql = f"""
        ALTER INDEX idx_semantic_memories_embedding_hnsw
        ALTER COLUMN embedding SET STATISTICS 500;
        """
        db.execute(text(sql))
        db.commit()

    except (ValueError, KeyError) as e:
        print(f"  ❌ HNSW 索引创建数据错误: {e}")
    except (OSError, IOError) as e:
        print(f"  ❌ HNSW 索引创建IO错误: {e}")
    except Exception as e:
        print(f"  ❌ HNSW 索引创建失败: {e}")

        if "concurrently" in str(e).lower():
            print("\n  提示: CONCURRENTLY 选项要求没有活跃的查询")
            retry = input("  尝试不使用 CONCURRENTLY 创建? (y/N): ").strip().lower()
            if retry == 'y':
                sql = f"""
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_embedding_hnsw
                ON semantic_memories
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = {m}, ef_construction = {ef_construction});
                """
                db.execute(text(sql))
                db.commit()
                print("  ✅ HNSW 索引创建成功 (不使用 CONCURRENTLY)")


def create_ivfflat_index(db, row_count: int = 0):
    """
    创建 IVFFlat 索引

    IVFFlat 参数说明:
    - lists: 倒排列表数量 (推荐: sqrt(n) 到 n/1000)
      - 值越大查询越快，但构建越慢
    """
    print("\n📦 创建 IVFFlat 索引...")

    if row_count > 0:
        lists = max(100, int(row_count ** 0.5))
        print(f"  推荐 lists 数: {lists} (基于数据量 {row_count})")
    else:
        lists = 100

    custom = input("使用自定义 lists? (y/N, 默认 100): ").strip().lower()
    if custom == 'y':
        try:
            lists_input = input(f"  lists (倒排列表数): ").strip()
            if lists_input:
                lists = int(lists_input)
        except ValueError:
            print("  使用推荐值")

    print(f"  参数: lists={lists}")

    try:
        sql = f"""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_semantic_memories_embedding_ivfflat
        ON semantic_memories
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = {lists});
        """
        db.execute(text(sql))
        db.commit()
        print("  ✅ IVFFlat 索引创建成功")

    except (ValueError, KeyError) as e:
        print(f"  ❌ IVFFlat 索引创建数据错误: {e}")
    except (OSError, IOError) as e:
        print(f"  ❌ IVFFlat 索引创建IO错误: {e}")
    except Exception as e:
        print(f"  ❌ IVFFlat 索引创建失败: {e}")

        if "concurrently" in str(e).lower():
            print("\n  提示: CONCURRENTLY 选项要求没有活跃的查询")
            retry = input("  尝试不使用 CONCURRENTLY 创建? (y/N): ").strip().lower()
            if retry == 'y':
                sql = f"""
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_embedding_ivfflat
                ON semantic_memories
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = {lists});
                """
                db.execute(text(sql))
                db.commit()
                print("  ✅ IVFFlat 索引创建成功 (不使用 CONCURRENTLY)")


def create_metadata_index(db):
    """
    创建元数据过滤索引

    用于加速元数据过滤查询
    """
    print("\n📦 创建元数据过滤索引...")

    indexes = [
        ("idx_semantic_memories_source", "source"),
        ("idx_semantic_memories_created_at", "created_at"),
        ("idx_semantic_memories_user_id", "user_id"),
    ]

    for idx_name, column in indexes:
        try:
            sql = f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name}
            ON semantic_memories ({column});
            """
            db.execute(text(sql))
            db.commit()
            print(f"  ✅ {column} 索引创建成功")
        except (ValueError, KeyError) as e:
            print(f"  ⚠️ {column} 索引创建数据错误: {e}")
        except (OSError, IOError) as e:
            print(f"  ⚠️ {column} 索引创建IO错误: {e}")
        except Exception as e:
            print(f"  ⚠️ {column} 索引创建失败: {e}")

    try:
        sql = """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_semantic_memories_metadata_gin
        ON semantic_memories USING gin (memory_metadata jsonb_path_ops);
        """
        db.execute(text(sql))
        db.commit()
        print("  ✅ JSON 元数据 GIN 索引创建成功")
    except (ValueError, KeyError) as e:
        print(f"  ⚠️ JSON 元数据索引创建数据错误: {e}")
    except (OSError, IOError) as e:
        print(f"  ⚠️ JSON 元数据索引创建IO错误: {e}")
    except Exception as e:
        print(f"  ⚠️ JSON 元数据索引创建失败: {e}")


def show_index_stats(db):
    """显示索引统计信息"""
    print("\n📊 索引统计:")

    try:
        result = db.execute(text("""
            SELECT
                indexname,
                pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
            AND indexname LIKE '%semantic_memories%'
            ORDER BY indexname;
        """))
        rows = result.fetchall()

        if rows:
            print(f"\n  {'索引名':<50} {'大小':<12} {'扫描次数':<10} {'读取':<10} {'命中':<10}")
            print("  " + "-" * 95)
            for row in rows:
                print(f"  {row[0]:<50} {row[1]:<12} {row[2]:<10} {row[3]:<10} {row[4]:<10}")
        else:
            print("  无索引统计信息")

        result = db.execute(text("""
            SELECT
                pg_size_pretty(pg_total_relation_size('semantic_memories')) as total_size,
                pg_size_pretty(pg_relation_size('semantic_memories')) as table_size,
                pg_size_pretty(pg_indexes_size('semantic_memories')) as index_size,
                (SELECT COUNT(*) FROM semantic_memories) as row_count
        """))
        row = result.fetchone()

        print(f"\n  表统计:")
        print(f"    总大小: {row[0]}")
        print(f"    表大小: {row[1]}")
        print(f"    索引大小: {row[2]}")
        print(f"    行数: {row[3]}")

    except (ValueError, KeyError) as e:
        print(f"\n  无法获取统计信息数据错误: {e}")
    except (OSError, IOError) as e:
        print(f"\n  无法获取统计信息IO错误: {e}")
    except Exception as e:
        print(f"\n  无法获取统计信息: {e}")


def verify_pgvector():
    """验证 pgvector 扩展是否已启用"""
    from app.db.session import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        result = db.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        row = result.fetchone()

        if row:
            print(f"✅ pgvector 扩展已启用: {row}")
            return True
        else:
            print("❌ pgvector 扩展未启用")
            print("\n请先执行:")
            print("  CREATE EXTENSION IF NOT EXISTS vector;")
            return False
    except (ValueError, KeyError) as e:
        print(f"❌ 无法检查 pgvector 数据错误: {e}")
        return False
    except (OSError, IOError) as e:
        print(f"❌ 无法检查 pgvector IO错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 无法检查 pgvector: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("🔍 检查 pgvector 扩展...\n")

    if verify_pgvector():
        create_vector_indexes()
    else:
        print("\n请先在 PostgreSQL 中启用 pgvector 扩展:")
        print("  psql -U postgres -d your_database -c \"CREATE EXTENSION IF NOT EXISTS vector;\"")
