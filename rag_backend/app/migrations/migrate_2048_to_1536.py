"""
向量维度迁移脚本 (2048 -> 1536)

将数据库中的向量从 2048 维降维到 1536 维
适配新的 embedding 模型配置

使用场景：
1. 将 chat_messages 表的 embedding 从 2048 降维到 1536
2. 将 semantic_memories 表的 embedding 从 2048 降维到 1536
3. 适配 zhipu embedding-3、openai text-embedding-3-small 等 1536 维模型

⚠️ 重要：
- 此脚本使用 PCA 降维，可能会损失一些信息
- 建议在测试环境先运行，确认无误后再在生产环境运行
- 建议先备份数据库

Author: RAG Backend Team
Date: 2026-04-04
"""

import os
import sys
import logging
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.decomposition import PCA
from typing import List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)


class Vector2048To1536Migrator:
    """
    2048维到1536维的向量迁移器
    
    使用 PCA 将 2048 维向量降维到 1536 维
    """
    
    def __init__(
        self,
        db_url: str,
        table_name: str,
        embedding_column: str = "embedding",
        batch_size: int = 1000
    ):
        """
        初始化迁移器
        
        Args:
            db_url: 数据库连接 URL
            table_name: 表名 (chat_messages 或 semantic_memories)
            embedding_column: 向量列名
            batch_size: 每批处理的向量数量
        """
        self.engine = create_engine(db_url)
        self.table_name = table_name
        self.embedding_column = embedding_column
        self.batch_size = batch_size
        self.source_dimensions = 2048
        self.target_dimensions = 1536
        
    def get_current_dimensions(self) -> int:
        """获取当前向量维度"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT atttypmod - 4 AS dimensions
                    FROM pg_attribute
                    WHERE attrelid = '{self.table_name}'::regclass
                    AND attname = '{self.embedding_column}';
                """))
                row = result.fetchone()
                return row[0] if row else 0
        except (ValueError, KeyError) as e:
            logger.error(f"获取当前维度数据失败: {e}")
            return 0
        except (OSError, IOError) as e:
            logger.error(f"获取当前维度IO失败: {e}")
            return 0
        except Exception as e:
            logger.error(f"获取当前维度失败: {e}")
            return 0
    
    def get_record_count(self) -> int:
        """获取需要处理的记录数"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {self.table_name}
                    WHERE {self.embedding_column} IS NOT NULL;
                """))
                return result.fetchone()[0]
        except (ValueError, KeyError) as e:
            logger.error(f"获取记录数数据失败: {e}")
            return 0
        except (OSError, IOError) as e:
            logger.error(f"获取记录数IO失败: {e}")
            return 0
        except Exception as e:
            logger.error(f"获取记录数失败: {e}")
            return 0
    
    def load_vectors(self, offset: int = 0, limit: int = None) -> Tuple[List[tuple], np.ndarray]:
        """
        加载向量数据
        
        Args:
            offset: 起始偏移
            limit: 限制数量
            
        Returns:
            (id列表, 向量数组)
        """
        limit = limit or self.batch_size
        
        with self.engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT id, {self.embedding_column}
                FROM {self.table_name}
                WHERE {self.embedding_column} IS NOT NULL
                ORDER BY id
                OFFSET :offset LIMIT :limit;
            """), {"offset": offset, "limit": limit})
            
            ids = []
            vectors = []
            
            for row in result:
                ids.append((row[0],))
                vector = np.array(row[1])
                vectors.append(vector)
            
            return ids, np.array(vectors) if vectors else np.array([])
    
    def reduce_dimensions(self, vectors: np.ndarray) -> np.ndarray:
        """
        使用 PCA 降维
        
        Args:
            vectors: 原始向量数组 (n_samples, 2048)
            
        Returns:
            降维后的向量数组 (n_samples, 1536)
        """
        if len(vectors) == 0:
            return np.array([])
        
        pca = PCA(n_components=self.target_dimensions)
        reduced = pca.fit_transform(vectors)
        
        logger.info(f"PCA 解释方差比例: {pca.explained_variance_ratio_.sum():.4f}")
        
        return reduced
    
    def update_vectors(self, ids: List[tuple], vectors: np.ndarray) -> int:
        """
        更新向量数据
        
        Args:
            ids: ID 列表
            vectors: 向量数组
            
        Returns:
            更新的记录数
        """
        if len(ids) == 0:
            return 0
        
        with self.engine.connect() as conn:
            count = 0
            for i, (record_id,) in enumerate(ids):
                vector = vectors[i].tolist()
                conn.execute(text(f"""
                    UPDATE {self.table_name}
                    SET {self.embedding_column} = :vector::vector
                    WHERE id = :id;
                """), {"vector": str(vector), "id": record_id})
                count += 1
                
                if (i + 1) % 100 == 0:
                    conn.commit()
                    logger.info(f"已更新 {i + 1}/{len(ids)} 条记录")
            
            conn.commit()
            return count
    
    def migrate(self, dry_run: bool = False) -> bool:
        """
        执行迁移
        
        Args:
            dry_run: 是否为试运行（不实际修改数据）
            
        Returns:
            是否成功
        """
        logger.info("=" * 60)
        logger.info(f"开始向量维度迁移: {self.table_name}")
        logger.info(f"源维度: {self.source_dimensions} -> 目标维度: {self.target_dimensions}")
        logger.info("=" * 60)
        
        current_dims = self.get_current_dimensions()
        if current_dims == 0:
            logger.error("无法获取当前向量维度，请检查表名和列名是否正确")
            return False
        
        logger.info(f"当前向量维度: {current_dims}")
        
        if current_dims != self.source_dimensions:
            logger.warning(f"当前维度 ({current_dims}) 与源维度 ({self.source_dimensions}) 不匹配")
            if current_dims == self.target_dimensions:
                logger.info("已经是目标维度，无需迁移")
                return True
        
        total_records = self.get_record_count()
        logger.info(f"需要处理的记录数: {total_records}")
        
        if total_records == 0:
            logger.info("没有需要处理的记录")
            return True
        
        if dry_run:
            logger.info("⚠️ 试运行模式，不会实际修改数据")
        
        total_processed = 0
        total_offset = 0
        
        while total_offset < total_records:
            logger.info(f"\n处理批次: {total_offset + 1} - {min(total_offset + self.batch_size, total_records)}")
            
            ids, vectors = self.load_vectors(offset=total_offset, limit=self.batch_size)
            
            if len(vectors) == 0:
                break
            
            logger.info(f"加载了 {len(vectors)} 条向量")
            
            reduced_vectors = self.reduce_dimensions(vectors)
            
            if not dry_run:
                updated = self.update_vectors(ids, reduced_vectors)
                logger.info(f"更新了 {updated} 条记录")
            else:
                logger.info(f"试运行: 将更新 {len(ids)} 条记录")
            
            total_processed += len(ids)
            total_offset += self.batch_size
            
            logger.info(f"进度: {total_processed}/{total_records} ({(total_processed/total_records*100):.1f}%)")
        
        logger.info("=" * 60)
        logger.info(f"迁移完成! 共处理 {total_processed} 条记录")
        logger.info("=" * 60)
        
        if not dry_run:
            logger.info("\n⚠️ 重要提醒:")
            logger.info("1. 现在需要修改数据库表结构以匹配新的向量维度")
            logger.info("2. 运行以下 SQL 修改表结构:")
            logger.info(f"   ALTER TABLE {self.table_name} ALTER COLUMN {self.embedding_column} TYPE vector({self.target_dimensions});")
            logger.info("\n3. 如果之前有向量索引，可能需要重建索引")
        
        return True


def main():
    """主函数"""
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logger.error("请设置 DATABASE_URL 环境变量")
        logger.info("示例: export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'")
        sys.exit(1)
    
    tables_to_migrate = [
        ("chat_messages", "embedding"),
        ("semantic_memories", "embedding"),
    ]
    
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        logger.info("⚠️ 试运行模式，不会实际修改数据")
    
    for table_name, column_name in tables_to_migrate:
        migrator = Vector2048To1536Migrator(
            db_url=db_url,
            table_name=table_name,
            embedding_column=column_name,
            batch_size=1000
        )
        
        try:
            migrator.migrate(dry_run=dry_run)
        except (ValueError, KeyError) as e:
            logger.error(f"迁移 {table_name} 数据失败: {e}", exc_info=True)
            continue
        except (OSError, IOError) as e:
            logger.error(f"迁移 {table_name} IO失败: {e}", exc_info=True)
            continue
        except Exception as e:
            logger.error(f"迁移 {table_name} 失败: {e}", exc_info=True)
            continue


if __name__ == "__main__":
    main()
