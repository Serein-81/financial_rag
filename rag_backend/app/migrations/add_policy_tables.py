"""
政策智能更新系统 - 数据库迁移脚本

创建政策相关数据表:
- policies: 政策主表
- policy_relations: 政策关系表
- enterprise_policy_matches: 企业-政策匹配表

使用方法:
    python -m app.migrations.add_policy_tables

Author: RAG Backend Team
Date: 2026-04-03
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def create_policy_tables():
    """
    创建政策相关数据表
    """
    from app.db.session import SessionLocal
    from sqlalchemy import text

    print("=" * 60)
    print("政策智能更新系统 - 数据库迁移")
    print("=" * 60)

    db = SessionLocal()
    try:
        print("\n[1/5] 检查 policies 表...")
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'policies'
            )
        """))
        if result.fetchone()[0]:
            print("  ✓ policies 表已存在，跳过创建")
        else:
            print("  创建 policies 表...")
            db.execute(text("""
                CREATE TABLE policies (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    policy_id VARCHAR(100) UNIQUE NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    
                    source_url VARCHAR(500),
                    source_name VARCHAR(100) NOT NULL,
                    
                    published_date TIMESTAMP WITH TIME ZONE,
                    effective_date TIMESTAMP WITH TIME ZONE,
                    expiry_date TIMESTAMP WITH TIME ZONE,
                    
                    industries TEXT[] DEFAULT '{}',
                    regions TEXT[] DEFAULT '{}',
                    scales TEXT[] DEFAULT '{}',
                    tax_types TEXT[] DEFAULT '{}',
                    
                    embedding REAL[],
                    
                    tags TEXT[] DEFAULT '{}',
                    
                    status VARCHAR(20) DEFAULT 'active' NOT NULL,
                    priority VARCHAR(20) DEFAULT 'medium' NOT NULL,
                    
                    version VARCHAR(50) DEFAULT '1.0',
                    view_count INTEGER DEFAULT 0,
                    meta_info JSONB DEFAULT '{}',
                    
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX ix_policies_policy_id ON policies(policy_id)"))
            db.execute(text("CREATE INDEX ix_policies_status ON policies(status)"))
            db.execute(text("CREATE INDEX ix_policies_priority ON policies(priority)"))
            db.execute(text("CREATE INDEX ix_policies_published_date ON policies(published_date)"))
            db.execute(text("CREATE INDEX ix_policies_effective_date ON policies(effective_date)"))
            db.execute(text("CREATE INDEX ix_policies_status_priority ON policies(status, priority)"))
            print("  ✓ policies 表创建完成")

        print("\n[2/5] 检查 policy_relations 表...")
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'policy_relations'
            )
        """))
        if result.fetchone()[0]:
            print("  ✓ policy_relations 表已存在，跳过创建")
        else:
            print("  创建 policy_relations 表...")
            db.execute(text("""
                CREATE TABLE policy_relations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_policy_id UUID NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
                    target_policy_id UUID NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
                    relation_type VARCHAR(20) DEFAULT 'related' NOT NULL,
                    description VARCHAR(500),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_policy_id, target_policy_id)
                )
            """))
            db.execute(text("CREATE INDEX ix_policy_relations_source ON policy_relations(source_policy_id)"))
            db.execute(text("CREATE INDEX ix_policy_relations_target ON policy_relations(target_policy_id)"))
            print("  ✓ policy_relations 表创建完成")

        print("\n[3/5] 检查 enterprise_policy_matches 表...")
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'enterprise_policy_matches'
            )
        """))
        if result.fetchone()[0]:
            print("  ✓ enterprise_policy_matches 表已存在，跳过创建")
        else:
            print("  创建 enterprise_policy_matches 表...")
            db.execute(text("""
                CREATE TABLE enterprise_policy_matches (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    enterprise_id VARCHAR(100) NOT NULL,
                    policy_id UUID NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
                    match_score REAL DEFAULT 0.0,
                    match_reasons JSONB DEFAULT '[]',
                    notification_status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    match_status VARCHAR(20) DEFAULT 'active' NOT NULL,
                    notified_at TIMESTAMP WITH TIME ZONE,
                    acknowledged_at TIMESTAMP WITH TIME ZONE,
                    dismissed_at TIMESTAMP WITH TIME ZONE,
                    feedback JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(enterprise_id, policy_id)
                )
            """))
            db.execute(text("CREATE INDEX ix_enterprise_policy_enterprise ON enterprise_policy_matches(enterprise_id)"))
            db.execute(text("CREATE INDEX ix_enterprise_policy_policy ON enterprise_policy_matches(policy_id)"))
            db.execute(text("CREATE INDEX ix_enterprise_policy_notification ON enterprise_policy_matches(notification_status)"))
            print("  ✓ enterprise_policy_matches 表创建完成")

        print("\n[4/5] 创建向量索引...")
        result = db.execute(text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'policies' 
            AND indexname LIKE '%embedding%'
        """))
        if result.fetchone():
            print("  ✓ policies 向量索引已存在")
        else:
            print("  创建 policies 向量索引 (HNSW)...")
            db.execute(text("""
                CREATE INDEX ix_policies_embedding_hnsw 
                ON policies 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """))
            print("  ✓ 向量索引创建完成")

        print("\n[5/5] 提交事务...")
        db.commit()

        print("\n" + "=" * 60)
        print("迁移完成!")
        print("=" * 60)
        print("\n已创建的表:")
        print("  - policies (政策主表)")
        print("  - policy_relations (政策关系表)")
        print("  - enterprise_policy_matches (企业-政策匹配表)")
        print("\n已创建的索引:")
        print("  - 主键索引 (id)")
        print("  - 唯一索引 (policy_id, enterprise_id+policy_id)")
        print("  - 业务索引 (status, priority, source_policy_id, target_policy_id等)")
        print("  - 向量索引 (HNSW)")
        print("\n下一步:")
        print("  1. 运行测试验证迁移")
        print("  2. 开始第二阶段: 核心Agent开发")
        print("=" * 60)

    except (ValueError, KeyError) as e:
        db.rollback()
        print(f"\n✗ 迁移数据失败: {e}")
    except (OSError, IOError) as e:
        db.rollback()
        print(f"\n✗ 迁移IO失败: {e}")
    except Exception as e:
        db.rollback()
        print(f"\n✗ 迁移失败: {e}")
        raise
    finally:
        db.close()


def rollback_policy_tables():
    """
    回滚迁移（删除政策相关表）
    """
    from app.db.session import SessionLocal
    from sqlalchemy import text

    print("=" * 60)
    print("政策智能更新系统 - 回滚迁移")
    print("=" * 60)
    print("\n警告: 此操作将删除所有政策相关数据和表!")
    print("-" * 60)

    confirm = input("\n确认删除? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("\n已取消回滚")
        return

    db = SessionLocal()
    try:
        print("\n删除数据表...")
        db.execute(text("DROP TABLE IF EXISTS enterprise_policy_matches CASCADE"))
        print("  ✓ enterprise_policy_matches 表已删除")
        db.execute(text("DROP TABLE IF EXISTS policy_relations CASCADE"))
        print("  ✓ policy_relations 表已删除")
        db.execute(text("DROP TABLE IF EXISTS policies CASCADE"))
        print("  ✓ policies 表已删除")

        db.commit()

        print("\n" + "=" * 60)
        print("回滚完成!")
        print("=" * 60)

    except (ValueError, KeyError) as e:
        db.rollback()
        print(f"\n✗ 回滚数据失败: {e}")
    except (OSError, IOError) as e:
        db.rollback()
        print(f"\n✗ 回滚IO失败: {e}")
    except Exception as e:
        db.rollback()
        print(f"\n✗ 回滚失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='政策数据库迁移工具')
    parser.add_argument('--rollback', action='store_true', help='回滚迁移')
    args = parser.parse_args()

    if args.rollback:
        rollback_policy_tables()
    else:
        create_policy_tables()
