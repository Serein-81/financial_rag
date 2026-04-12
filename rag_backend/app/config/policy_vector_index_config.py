# app/config/policy_vector_index_config.py
"""
政策向量索引配置文件

记录政策表向量索引的配置和参数

Author: RAG Backend Team
Date: 2026-04-03
"""

POLICY_VECTOR_INDEX_CONFIG = {
    "table_name": "policies",
    "embedding_column": "embedding",
    
    "index_type": "hnsw",
    
    "hnsw_params": {
        "m": 16,
        "ef_construction": 64,
        "ef_search": 40,
        "distance_func": "cosine"
    },
    
    "description": """
    HNSW (Hierarchical Navigable Small World) 索引配置
    
    参数说明:
    - m: 每个节点的最大连接数
      - 值越大，召回率越高，但内存占用越大
      - 推荐范围: 8-64
      - 当前值: 16
    
    - ef_construction: 构建时的动态列表大小
      - 值越大，构建时间越长，但索引质量越好
      - 推荐范围: 32-512
      - 当前值: 64
    
    - ef_search: 搜索时的动态列表大小
      - 值越大，召回率越高，但搜索速度越慢
      - 推荐范围: 16-256
      - 当前值: 40
    
    - distance_func: 距离函数
      - cosine: 余弦距离（推荐用于文本相似性）
      - l2: 欧氏距离
      - ip: 内积
    """,
    
    "usage_guidelines": """
    使用建议:
    1. 查询示例:
       SELECT * FROM policies 
       ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
       LIMIT 10;
    
    2. 性能调优:
       - 小数据量 (< 1万): 使用默认参数
       - 中数据量 (1-10万): m=16, ef=64
       - 大数据量 (> 10万): m=32, ef=128
    
    3. 监控指标:
       - 查询响应时间
       - 召回率
       - 内存占用
    """,
    
    "maintenance": """
    维护指南:
    1. 重建索引:
       REINDEX INDEX ix_policies_embedding_hnsw;
    
    2. 查看索引大小:
       SELECT pg_size_pretty(pg_relation_size('ix_policies_embedding_hnsw'));
    
    3. 查看索引使用情况:
       SELECT * FROM pg_stat_user_indexes 
       WHERE indexname = 'ix_policies_embedding_hnsw';
    """,
    
    "created_date": "2026-04-03",
    "created_by": "AI Assistant"
}


ENTITLEPRISE_POLICY_MATCH_INDEX_CONFIG = {
    "table_name": "enterprise_policy_matches",
    
    "indexes": [
        {
            "name": "ix_enterprise_policy_enterprise",
            "columns": ["enterprise_id"],
            "type": "btree",
            "purpose": "按企业ID查询"
        },
        {
            "name": "ix_enterprise_policy_policy",
            "columns": ["policy_id"],
            "type": "btree",
            "purpose": "按政策ID查询"
        },
        {
            "name": "ix_enterprise_policy_notification",
            "columns": ["notification_status"],
            "type": "btree",
            "purpose": "查询待通知的匹配"
        },
        {
            "name": "ix_enterprise_policy_unique",
            "columns": ["enterprise_id", "policy_id"],
            "type": "btree",
            "purpose": "唯一约束，防止重复"
        }
    ],
    
    "description": """
    企业-政策匹配表索引配置
    
    索引策略:
    1. 复合索引: (enterprise_id, policy_id) 用于唯一约束
    2. 单列索引: enterprise_id 用于按企业查询
    3. 单列索引: policy_id 用于按政策查询
    4. 单列索引: notification_status 用于批量通知任务
    """,
    
    "created_date": "2026-04-03",
    "created_by": "AI Assistant"
}


def get_policy_index_sql() -> str:
    """
    获取创建政策向量索引的SQL语句
    """
    return """
    CREATE INDEX IF NOT EXISTS ix_policies_embedding_hnsw 
    ON policies 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
    """


def get_match_indexes_sql() -> list:
    """
    获取创建企业-政策匹配表索引的SQL语句
    """
    return [
        """
        CREATE INDEX IF NOT EXISTS ix_enterprise_policy_enterprise 
        ON enterprise_policy_matches(enterprise_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_enterprise_policy_policy 
        ON enterprise_policy_matches(policy_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_enterprise_policy_notification 
        ON enterprise_policy_matches(notification_status);
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_enterprise_policy_unique 
        ON enterprise_policy_matches(enterprise_id, policy_id);
        """
    ]
