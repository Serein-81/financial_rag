"""
向量降维脚本

使用 PCA 将高维向量降维到 pgvector 支持的范围内
pgvector 索引最大支持 2000 维

使用场景：
1. 从 embedding-3 (2048维) 降维到 2000维以下
2. 为后续创建 HNSW/IVFFlat 索引做准备

Author: RAG Backend Team
Date: 2026-04-03
"""

import os
import sys
import logging
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.decomposition import PCA
from typing import List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VectorDimensionReducer:
    """
    向量降维处理器
    
    使用 PCA 将高维向量降维到指定维度
    """
    
    def __init__(
        self,
        db_url: str,
        table_name: str = "semantic_memories",
        embedding_column: str = "embedding",
        target_dimensions: int = 1024,
        batch_size: int = 1000
    ):
        """
        初始化降维处理器
        
        Args:
            db_url: 数据库连接 URL
            table_name: 表名
            embedding_column: 向量列名
            target_dimensions: 目标维度数
            batch_size: 每批处理的向量数量
        """
        self.engine = create_engine(db_url)
        self.table_name = table_name
        self.embedding_column = embedding_column
        self.target_dimensions = target_dimensions
        self.batch_size = batch_size
        
    def get_current_dimensions(self) -> int:
        """获取当前向量维度"""
        with self.engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT atttypmod - 4 AS dimensions
                FROM pg_attribute
                WHERE attrelid = '{self.table_name}'::regclass
                AND attname = '{self.embedding_column}';
            """))
            row = result.fetchone()
            return row[0] if row else 0
    
    def load_vectors(self, limit: Optional[int] = None) -> Tuple[List[int], np.ndarray]:
        """
        加载向量数据
        
        Returns:
            (id列表, 向量数组)
        """
        with self.engine.connect() as conn:
            count_query = f"SELECT COUNT(*) FROM {self.table_name}"
            total = conn.execute(text(count_query)).scalar()
            
            logger.info(f"正在加载 {total} 条向量...")
            
            query = f"""
                SELECT id, {self.embedding_column}
                FROM {self.table_name}
                ORDER BY id
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            result = conn.execute(text(query))
            rows = result.fetchall()
            
            ids = []
            vectors = []
            
            for row in rows:
                ids.append(row[0])
                vector_str = row[1]
                
                if isinstance(vector_str, str):
                    vector = np.array([float(x) for x in vector_str.strip('[]{}').split(',')])
                else:
                    vector = np.array(vector_str)
                
                vectors.append(vector)
            
            return ids, np.array(vectors)
    
    def reduce_dimensions(self, vectors: np.ndarray) -> np.ndarray:
        """
        使用 PCA 降维
        
        Args:
            vectors: 原始向量数组 (n_samples, n_features)
            
        Returns:
            降维后的向量数组 (n_samples, target_dimensions)
        """
        n_samples, n_features = vectors.shape
        target_dims = min(self.target_dimensions, n_features - 1)
        
        if target_dims >= n_features:
            logger.info(f"目标维度 ({target_dims}) >= 当前维度 ({n_features})，无需降维")
            return vectors
        
        logger.info(f"正在将 {n_features} 维向量降维到 {target_dims} 维...")
        
        pca = PCA(n_components=target_dims, random_state=42)
        reduced_vectors = pca.fit_transform(vectors)
        
        explained_variance = sum(pca.explained_variance_ratio_) * 100
        logger.info(f"PCA 降维完成，保留 {explained_variance:.2f}% 的信息")
        
        return reduced_vectors
    
    def save_vectors(self, ids: List[int], vectors: np.ndarray) -> int:
        """
        保存降维后的向量
        
        Returns:
            更新成功的向量数量
        """
        logger.info(f"正在保存 {len(ids)} 条降维后的向量...")
        
        with self.engine.connect() as conn:
            for i in range(0, len(ids), self.batch_size):
                batch_ids = ids[i:i + self.batch_size]
                batch_vectors = vectors[i:i + self.batch_size]
                
                for j, (id_val, vector) in enumerate(zip(batch_ids, batch_vectors)):
                    vector_str = f"[{','.join([str(x) for x in vector])}]"
                    
                    conn.execute(
                        text(f"""
                            UPDATE {self.table_name}
                            SET {self.embedding_column} = :vector
                            WHERE id = :id
                        """),
                        {"vector": vector_str, "id": id_val}
                    )
                
                conn.commit()
                logger.info(f"已保存 {min(i + self.batch_size, len(ids))}/{len(ids)} 条向量")
        
        return len(ids)
    
    def run(self, tables: Optional[List[str]] = None) -> bool:
        """
        执行降维流程
        
        Args:
            tables: 要处理的表列表，None 则处理默认表
            
        Returns:
            是否全部成功
        """
        tables = tables or [self.table_name]
        success = True
        
        for table in tables:
            logger.info(f"\n{'='*60}")
            logger.info(f"处理表: {table}")
            logger.info(f"{'='*60}")
            
            try:
                original_dims = self.get_current_dimensions()
                logger.info(f"原始向量维度: {original_dims}")
                
                if original_dims <= 2000:
                    logger.info("向量维度已在 pgvector 索引限制内，跳过降维")
                    continue
                
                ids, vectors = self.load_vectors()
                
                if len(ids) == 0:
                    logger.warning(f"表 {table} 中没有向量数据")
                    continue
                
                reduced_vectors = self.reduce_dimensions(vectors)
                
                self.save_vectors(ids, reduced_vectors)
                
                new_dims = self.get_current_dimensions()
                logger.info(f"降维完成！新向量维度: {new_dims}")
                
            except (ValueError, KeyError) as e:
                logger.error(f"处理表 {table} 时数据出错: {e}")
                success = False
            except (OSError, IOError) as e:
                logger.error(f"处理表 {table} 时IO出错: {e}")
                success = False
            except Exception as e:
                logger.error(f"处理表 {table} 时出错: {e}")
                success = False
                continue
        
        return success


def create_hnsw_index(db_url: str, table_name: str, embedding_column: str) -> bool:
    """
    创建 HNSW 向量索引
    
    Args:
        db_url: 数据库连接 URL
        table_name: 表名
        embedding_column: 向量列名
        
    Returns:
        是否成功
    """
    logger.info(f"\n{'='*60}")
    logger.info("创建 HNSW 向量索引")
    logger.info(f"{'='*60}")
    
    try:
        with create_engine(db_url).connect() as conn:
            current_dims = conn.execute(text(f"""
                SELECT atttypmod - 4 AS dimensions
                FROM pg_attribute
                WHERE attrelid = '{table_name}'::regclass
                AND attname = '{embedding_column}';
            """)).fetchone()[0]
            
            logger.info(f"当前向量维度: {current_dims}")
            
            if current_dims > 2000:
                logger.error(f"向量维度 ({current_dims}) 超过 pgvector 索引限制 (2000)")
                logger.error("请先运行降维脚本")
                return False
            
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS {table_name}_{embedding_column}_hnsw
                ON {table_name}
                USING hnsw ({embedding_column} vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            conn.commit()
            
            logger.info("HNSW 索引创建成功！")
            return True
            
    except (ValueError, KeyError) as e:
        logger.error(f"创建索引数据失败: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"创建索引IO失败: {e}")
        return False
    except Exception as e:
        logger.error(f"创建索引失败: {e}")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="向量降维脚本")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/rag_db"),
        help="数据库连接 URL"
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        default=["semantic_memories"],
        help="要处理的表列表"
    )
    parser.add_argument(
        "--target-dim",
        type=int,
        default=1024,
        help="目标维度数"
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="跳过索引创建"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("向量降维脚本")
    logger.info("=" * 60)
    logger.info(f"数据库: {args.db_url}")
    logger.info(f"目标维度: {args.target_dim}")
    logger.info(f"处理表: {args.tables}")
    logger.info("=" * 60)
    
    reducer = VectorDimensionReducer(
        db_url=args.db_url,
        target_dimensions=args.target_dim,
        batch_size=500
    )
    
    if not reducer.run(args.tables):
        logger.error("降维过程出现错误")
        sys.exit(1)
    
    if not args.skip_index:
        for table in args.tables:
            create_hnsw_index(args.db_url, table, "embedding")
    
    logger.info("\n" + "=" * 60)
    logger.info("全部完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
