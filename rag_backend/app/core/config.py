# app/core/config.py

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 1. 基础配置
    PROJECT_NAME: str = "RAG Knowledge Base"
    API_V1_STR: str = "/api/v1"

    # 2. 数据库配置 (变量名必须和 .env 文件里的一模一样)
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: str
    POSTGRES_DB: str

    # PgBouncer 配置 (用于 Transaction 模式)
    PGBOUNCER_ENABLED: bool = False  # 是否启用 PgBouncer
    PGBOUNCER_HOST: str = "127.0.0.1"  # PgBouncer 主机
    PGBOUNCER_PORT: int = 6432  # PgBouncer 端口
    PGBOUNCER_USER: Optional[str] = None  # PgBouncer 用户名（默认使用 POSTGRES_USER）
    PGBOUNCER_PASSWORD: Optional[str] = None  # PgBouncer 密码（默认使用 POSTGRES_PASSWORD）
    PGBOUNCER_POOL_MODE: str = "transaction"  # 连接池模式: transaction 或 session
    PGBOUNCER_DATABASE: Optional[str] = None  # PgBouncer 中的数据库名（默认使用 POSTGRES_DB）

    # 数据库连接池配置（优化用于 PgBouncer）
    DB_POOL_SIZE: int = 5  # 基础连接数（PgBouncer 模式下可以设小一些）
    DB_MAX_OVERFLOW: int = 5  # 最大溢出连接数
    DB_POOL_TIMEOUT: int = 30  # 连接获取超时（秒）
    DB_POOL_RECYCLE: int = 3600  # 连接回收时间（秒）

    # 3. 最终的连接字符串 (代码动态拼接，不需要在 env 里写)
    @property
    def DATABASE_URL(self) -> str:
        if self.PGBOUNCER_ENABLED:
            host = self.PGBOUNCER_HOST
            port = self.PGBOUNCER_PORT
            user = self.PGBOUNCER_USER or self.POSTGRES_USER
            password = self.PGBOUNCER_PASSWORD or self.POSTGRES_PASSWORD
            database = self.PGBOUNCER_DATABASE or self.POSTGRES_DB
            return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
        else:
            return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # 原始 PostgreSQL 连接字符串（绕过 PgBouncer）
    @property
    def POSTGRES_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # 4. 👇 【新增】认证与安全配置 (Security)
    # 这些变量 Pydantic 会去 .env 里找，找不到会用默认值
    SECRET_KEY: str  # 必填！
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 5. 👇 LLM 大模型配置
    # 当前使用的提供商：zhipu, openai, claude, minimax, xinference, huggingface, modelscope, baichuan, gpt, deepseek, qwen
    LLM_PROVIDER: str = "zhipu"
    
    # 默认智能体 LLM 配置（问候语、普通对话等）
    # 为空时使用 LLM_PROVIDER 的值
    LLM_PROVIDER_DEFAULT: str = ""
    
    # 专家智能体 LLM 配置（金融、税务、法律等专家）
    # 为空时所有智能体都使用 LLM_PROVIDER 或 LLM_PROVIDER_DEFAULT 的值
    # 可选：deepseek, qwen, zhipu, gpt, openai, claude, minimax 等
    LLM_PROVIDER_SPECIALIST: str = ""
    
    # Agent 模式配置
    # 支持的模式：react, plan, reflect
    AGENT_MODE: str = "react"
    
    # 工具来源配置
    # 支持的模式：cloud（云端 MCP）、local（本地）、auto（自动选择）
    # - cloud: 强制使用云端 MCP 工具
    # - local: 强制使用本地工具
    # - auto: 同时注册本地和云端工具（用于 Agent Discovery 显示）
    MCP_MODE: str = "auto"
    
    # 通用 LLM 重试配置
    LLM_MAX_RETRIES: int = 5
    LLM_BASE_DELAY: float = 2.0
    LLM_TIMEOUT_SECONDS: int = 600
    
    # 知识图谱提取配置
    KG_EXTRACTION_MODEL: str = "deepseek/deepseek-chat"  # 实体/关系提取模型
    EXTRACTION_MAX_RETRIES: int = 1  # 提取重试次数
    EXTRACTION_CONCURRENCY: int = 3  # 并发提取数量
    
    # GPT 配置（OpenRouter API）
    GPT_API_KEY: str = ""
    GPT_MODEL: str = "openai/gpt-5.4-nano"
    GPT_BASE_URL: str = "https://openrouter.ai/api/v1"
    GPT_VERIFY_SSL: bool = True
    
    # 智谱 AI 配置
    ZHIPU_API_KEY: str = ""
    ZHIPU_MODEL: str = "glm-4-flash"
    
    # OpenAI 配置（可选）
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    
    # Claude 配置（可选）
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-3-sonnet-20240229"
    CLAUDE_BASE_URL: str = "https://api.anthropic.com/v1"
    
    # MiniMax 配置 ⭐用户要求
    MINIMAX_API_KEY: str = ""
    MINIMAX_MODEL: str = "MiniMax-Text-01"
    MINIMAX_BASE_URL: str = "https://api.minimax.chat/v1"
    MINIMAX_GROUP_ID: str = ""
    
    # Xinference 配置（本地部署）
    XINFERENCE_API_KEY: str = ""
    XINFERENCE_MODEL: str = ""
    XINFERENCE_BASE_URL: str = "http://127.0.0.1:9997/v1"
    
    # HuggingFace 配置
    HUGGINGFACE_API_KEY: str = ""
    HUGGINGFACE_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    HUGGINGFACE_BASE_URL: str = "https://api-inference.huggingface.co/models"
    
    # ModelScope 配置（魔塔）
    MODELSCOPE_API_KEY: str = ""
    MODELSCOPE_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    MODELSCOPE_BASE_URL: str = "https://api.modelscope.cn/v1"
    
    # BaiChuan 配置（百川）
    BAICHUAN_API_KEY: str = ""
    BAICHUAN_MODEL: str = "baichuan4"
    BAICHUAN_BASE_URL: str = "https://api.baichuan-ai.com/v1"
    BAICHUAN_SECRET_KEY: str = ""
    
    # DeepSeek 配置（OpenRouter API）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek/deepseek-chat-v3-0324"
    DEEPSEEK_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEEPSEEK_VERIFY_SSL: bool = False
    
    # Qwen 配置（OpenRouter API）
    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen/qwen3.6-plus:free"
    QWEN_BASE_URL: str = "https://openrouter.ai/api/v1"
    QWEN_VERIFY_SSL: bool = False
    
    # 👇 Embedding 向量化配置
    # 当前使用的提供商：zhipu, openai, ollama, siliconflow
    EMBEDDING_PROVIDER: str = "zhipu"
    
    # 通用 Embedding 配置
    EMBEDDING_BATCH_SIZE: int = 16  # 批量处理大小
    EMBEDDING_MAX_RETRIES: int = 3  # 最大重试次数
    EMBEDDING_TIMEOUT: int = 60  # 超时时间（秒）
    
    # 智谱 AI Embedding 配置
    ZHIPU_EMBEDDING_MODEL: str = "embedding-3"
    
    # OpenAI Embedding 配置
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Ollama 本地部署 Embedding 配置
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # 硅基流动 Embedding 配置
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    
    # 硅基流动 Rerank 配置
    # 推荐模型：
    # - Pro/BAAI/bge-reranker-v2-m3: 智源BAAI出品，中文优化，精度高
    # - Qwen/Qwen3-Reranker-0.6B: Qwen3轻量版，速度快
    # - Qwen/Qwen3-Reranker-4B: Qwen3中等规模
    # - Qwen/Qwen3-Reranker-8B: Qwen3大规模，精度最高
    SILICONFLOW_RERANK_MODEL: str = "Pro/BAAI/bge-reranker-v2-m3"
    ENABLE_RERANK: bool = True
    RERANK_TOP_K: int = 10
    RERANK_MAX_CHARS: int = 512
    RERANK_SCORE_THRESHOLD: float = 0.5  # 相关性分数阈值，低于此分数的结果会被过滤
    
    # MinIO 配置
    MINIO_ENDPOINT: str = "127.0.0.1:9000"  # MinIO 服务端点（内部访问）
    MINIO_PUBLIC_ENDPOINT: str = "127.0.0.1:9000"  # MinIO 公开端点（浏览器访问）
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "documents"  # 修复：添加默认bucket配置
    MINIO_AVATAR_BUCKET: str = "avatars"
    
    # MinIO 增强配置
    MINIO_PREFIX_PATH: Optional[str] = None  # 存储路径前缀（如 "my_rag"）
    MINIO_DEFAULT_BUCKET: Optional[str] = None  # 默认桶名称（增强模块专用）
    MINIO_VERIFY_SSL: bool = True  # 是否验证 SSL 证书（False 支持自签名）
    MINIO_RETRY_MAX_ATTEMPTS: int = 3  # 最大重试次数
    MINIO_RETRY_DELAY: float = 1.0  # 初始重试延迟（秒）
    MINIO_RETRY_EXPONENTIAL: bool = True  # 是否使用指数退避


    # 和风天气 API 配置（专属订阅）
    QWEATHER_API_KEY: str = ""
    QWEATHER_WEATHER_HOST: str = ""  # 天气查询专属 Host
    QWEATHER_GEO_HOST: str = ""      # 地理位置查询专属 Host
    
    # 高德地图 API 配置
    GAODE_API_KEY: str = ""
    
    # Tavily 搜索 API 配置
    TAVILY_API_KEY: str = ""

    # 政策采集合规配置
    # 允许在线政策采集；采集只由手动接口触发，并保留 robots.txt 与访问频率限制。
    POLICY_ONLINE_CRAWL_ENABLED: bool = True
    POLICY_SAMPLE_FALLBACK_ENABLED: bool = True
    POLICY_REQUIRE_ROBOTS_TXT: bool = True
    POLICY_COLLECTOR_USER_AGENT: str = "PolicyCollector/1.0 (Enterprise Tax System; Contact: support@example.com)"
    
    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    
    # 记忆缓存配置
    ENABLE_MEMORY_CACHE: bool = True

    # 批量处理配置
    BATCH_MAX_CONCURRENCY: int = 10
    BATCH_PROGRESS_WS_ENABLED: bool = True

    # API 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    RATE_LIMIT_BURST_SIZE: int = 10
    RATE_LIMIT_STRATEGY: str = "sliding_window"  # sliding_window, token_bucket, fixed_window
    RATE_LIMIT_STORAGE: str = "memory"  # memory, redis
    MEMORY_CACHE_TTL: int = 1800
    MEMORY_CACHE_PREFIX: str = "memory:"
    
    # 智能存储调度配置
    ENABLE_STORAGE_TIERING: bool = False
    HOT_THRESHOLD: int = 10
    COLD_THRESHOLD: int = 2
    HOT_TTL: int = 3600
    COLD_BATCH_SIZE: int = 50
    
    # 阿里云短信服务配置
    ALIYUN_ACCESS_KEY_ID: str = ""
    ALIYUN_ACCESS_KEY_SECRET: str = ""
    ALIYUN_SMS_SIGN_NAME: str = ""
    ALIYUN_SMS_TEMPLATE_CODE: str = ""
    
    # 验证码配置
    SMS_CODE_LENGTH: int = 6
    SMS_CODE_EXPIRE: int = 300  # 验证码过期时间（秒）
    SMS_SEND_INTERVAL: int = 3600  # 发送间隔（秒），1小时
    SMS_DAILY_LIMIT: int = 3  # 每日发送次数限制
    
    # 知识图谱配置
    ENABLE_KNOWLEDGE_GRAPH: bool = False
    ENABLE_ENTITY_EXTRACTION: bool = False
    ENABLE_RELATION_EXTRACTION: bool = False
    ENABLE_COREFERENCE_RESOLUTION: bool = True  # 指代消解
    ENTITY_CONFIDENCE_THRESHOLD: float = 0.7  # 实体置信度阈值
    ENTITY_EXTRACTION_METHOD: str = "llm"  # llm 或 spacy
    ENTITY_EXTRACTION_MODEL: str = "glm-4-flash"
    
    # Neo4j 配置
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "REDACTED_NEO4J_PASSWORD"
    NEO4J_DATABASE: str = "neo4j"
    
    # 专家智能体类型列表
    SPECIALIST_AGENT_TYPES: set = {
        "finance", "tax", "legal", "financial", "taxation", "legislation",
        "finance_specialist", "tax_specialist", "legal_specialist",
        "FinanceSpecialist", "TaxSpecialist", "LegalSpecialist"
    }
    
    def get_llm_provider_for_agent(self, agent_type: str) -> str:
        """
        根据智能体类型获取合适的 LLM 提供商
        
        Args:
            agent_type: 智能体类型（如 "finance", "tax", "chat" 等）
            
        Returns:
            LLM 提供商名称
        """
        is_specialist = agent_type.lower() in self.SPECIALIST_AGENT_TYPES
        
        if is_specialist and self.LLM_PROVIDER_SPECIALIST:
            return self.LLM_PROVIDER_SPECIALIST
        
        if self.LLM_PROVIDER_DEFAULT:
            return self.LLM_PROVIDER_DEFAULT
        
        return self.LLM_PROVIDER

    # A2A 传输模式配置
    # 支持的模式：
    # - graph_state: LangGraph 状态黑板模式（当前 MVP）
    # - http: HTTP 远程调用（未来微服务形态）
    # - local: 本地进程通信（同服务器跨进程）
    A2A_TRANSPORT_MODE: str = "graph_state"

    # HTTP 传输配置（A2A_TRANSPORT_MODE=http 时使用）
    A2A_HTTP_BASE_URL: str = "http://localhost:8000"
    A2A_HTTP_TIMEOUT: float = 30.0
    A2A_HTTP_RETRY_TIMES: int = 3

    # Startup diagnostics. Keep this off by default to avoid noisy container logs.
    STARTUP_VERBOSE: bool = False

    model_config = {
        # 指定读取根目录下的 .env 文件
        "env_file": os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".env"
        ),
        "case_sensitive": True,
        "extra": "ignore"  # 忽略 .env 中多余的字段，防止报错
    }


settings = Settings()
