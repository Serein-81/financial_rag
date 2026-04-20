"""
LangGraph 完整集成指南

包含：
1. API 路由集成
2. 存储系统配置
3. LangSmith 监控集成
4. 最佳实践
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass
from app.langgraph.persistences import RedisCheckpointer, PostgresCheckpointer
from app.langgraph.monitoring import LangSmithMonitor

logger = logging.getLogger(__name__)


@dataclass
class LangGraphIntegrationConfig:
    """LangGraph 集成配置"""
    
    # ===== 持久化配置 =====
    persistence_type: str = "memory"  # memory | redis | postgres
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_seconds: int = 86400 * 7  # 7 天过期
    postgres_table: str = "langgraph_checkpoints"
    
    # ===== 监控配置 =====
    langsmith_enabled: bool = False
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "my-rag-backend"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    
    # ===== 性能配置 =====
    max_iterations: int = 10
    max_retries: int = 3
    enable_reflection: bool = True
    confidence_threshold: float = 0.7


class LangGraphIntegration:
    """
    LangGraph 集成管理器
    
    统一管理：
    - 持久化存储
    - 监控追踪
    - 工作流配置
    """
    
    def __init__(self, config: LangGraphIntegrationConfig):
        self.config = config
        self._checkpointer = None
        self._monitor = None
    
    async def initialize(self):
        """初始化集成组件"""
        await self._setup_checkpointer()
        await self._setup_monitor()
        logger.info("[LangGraph Integration] 初始化完成")
    
    async def _setup_checkpointer(self):
        """设置检查点存储"""
        if self.config.persistence_type == "redis":
            self._checkpointer = RedisCheckpointer(
                redis_url=self.config.redis_url,
                ttl_seconds=self.config.redis_ttl_seconds
            )
            logger.info(f"[Checkpointer] Redis: {self.config.redis_url}")
        
        elif self.config.persistence_type == "postgres":
            self._checkpointer = PostgresCheckpointer(
                table_name=self.config.postgres_table
            )
            logger.info(f"[Checkpointer] PostgreSQL: {self.config.postgres_table}")
        
        else:  # memory
            from langgraph.checkpoint.memory import MemorySaver
            self._checkpointer = MemorySaver()
            logger.info("[Checkpointer] Memory (无持久化)")
    
    async def _setup_monitor(self):
        """设置监控"""
        api_key = self.config.langsmith_api_key or os.getenv("LANGCHAIN_API_KEY")
        
        if self.config.langsmith_enabled and api_key:
            self._monitor = LangSmithMonitor(
                api_key=api_key,
                project_name=self.config.langsmith_project,
                endpoint=self.config.langsmith_endpoint,
                enabled=True
            )
            logger.info(f"[Monitor] LangSmith 已启用: {self.config.langsmith_project}")
        else:
            self._monitor = LangSmithMonitor(enabled=False)
            logger.info("[Monitor] LangSmith 已禁用")
    
    @property
    def checkpointer(self):
        """获取检查点存储"""
        return self._checkpointer
    
    @property
    def monitor(self):
        """获取监控器"""
        return self._monitor


# ===== 使用示例 =====

async def example_usage():
    """
    完整使用示例
    
    场景：用户询问"分析一下公司第一季度的财务和税务情况"
    """
    
    # 1. 初始化集成
    config = LangGraphIntegrationConfig(
        persistence_type="redis",
        redis_url="redis://localhost:6379/0",
        redis_ttl_seconds=86400 * 7,
        langsmith_enabled=True,
        langsmith_project="production-agent",
        langsmith_api_key=os.getenv("LANGCHAIN_API_KEY"),
        enable_reflection=True,
        confidence_threshold=0.7
    )
    
    integration = LangGraphIntegration(config)
    await integration.initialize()
    
    # 2. 在工作流中使用
    checkpointer = integration.checkpointer
    monitor = integration.monitor
    
    # 3. 示例：在节点执行时追踪
    async with monitor.trace("finance_specialist_node") as trace:
        trace["metadata"] = {
            "inputs": {
                "query": "分析第一季度财务情况",
                "session_id": "user_123"
            }
        }
        
        # 执行专家任务
        # result = await finance_specialist.run("分析第一季度财务情况")
        # 注意：实际使用时需要导入并实例化 finance_specialist
        
        trace["metadata"]["outputs"] = {
            # "result": result,
            "confidence": 0.85
        }
        
        # 记录 Token 使用
        monitor.log_token_usage(234, 89, 323)
    
    # 4. 保存检查点
    await checkpointer.put(
        thread_id="user_123_workflow_1",
        checkpoint={
            "current_node": "reflection",
            # "specialist_results": [{"finance": result}],
            "iteration": 1
        }
    )
    
    # 5. 工作流完成后，清理检查点
    await checkpointer.delete("user_123_workflow_1")
    
    # 6. 刷新监控数据
    await monitor.flush()


# ===== 环境配置指南 =====

"""
环境变量配置:

# LangSmith (可选)
LANGCHAIN_API_KEY=your_api_key
LANGCHAIN_PROJECT=production-agent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_TRACING_V2=true  # 启用 v2 追踪

# Redis (可选，用于工作流持久化)
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your_password

# PostgreSQL (可选，用于工作流持久化)
DATABASE_URL=postgresql://user:pass@localhost/dbname

# 配置优先级:
# 1. 代码中的显式配置 (优先级最高)
# 2. 环境变量
# 3. 配置文件 (config.yaml)
# 4. 默认值
"""
