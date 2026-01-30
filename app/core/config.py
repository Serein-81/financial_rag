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

    # 5. 👇 智谱 API Key
    ZHIPU_API_KEY: str = ""

    class Config:
        # 指定读取根目录下的 .env 文件
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".env"
        )
        case_sensitive = True
        extra = "ignore"  # 忽略 .env 中多余的字段，防止报错


settings = Settings()