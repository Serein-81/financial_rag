# app/core/config.py
import os
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

    # 3. 最终的连接字符串 (代码动态拼接，不需要在 env 里写)
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # 4. 👇 【新增】认证与安全配置 (Security)
    # 这些变量 Pydantic 会去 .env 里找，找不到会用默认值
    SECRET_KEY: str  # 必填！
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 5. 👇 LLM 大模型配置
    # 当前使用的提供商：zhipu, openai, claude
    LLM_PROVIDER: str = "zhipu"
    
    # Agent 模式配置
    # 支持的模式：react, plan, reflect
    AGENT_MODE: str = "react"
    
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
    
    # MinIO 配置
    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "documents"  # 修复：添加默认bucket配置
    MINIO_AVATAR_BUCKET: str = "avatars"


    # 和风天气 API 配置（专属订阅）
    QWEATHER_API_KEY: str = ""
    QWEATHER_WEATHER_HOST: str = ""  # 天气查询专属 Host
    QWEATHER_GEO_HOST: str = ""      # 地理位置查询专属 Host
    
    # 高德地图 API 配置
    GAODE_API_KEY: str = ""
    
    # Tavily 搜索 API 配置
    TAVILY_API_KEY: str = ""
    
    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    
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

    class Config:
        # 指定读取根目录下的 .env 文件
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".env"
        )
        case_sensitive = True
        extra = "ignore"  # 忽略 .env 中多余的字段，防止报错


settings = Settings()