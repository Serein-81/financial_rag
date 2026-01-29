import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 1. 基础配置
    PROJECT_NAME: str
    API_V1_STR: str
    
    # 这些变量名必须和 .env 文件里的一模一样
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: str
    POSTGRES_DB: str

    # 3. 最终的连接字符串
    DATABASE_URL: str

    # 👇 【新增】智谱 API Key
    # Pydantic 会自动去 .env 里找名字叫 ZHIPU_API_KEY 的值填进来
    ZHIPU_API_KEY: str = ""

    class Config:
        # 指定读取根目录下的 .env 文件
        # 使用 os 模块动态获取绝对路径，防止“找不到文件”的错误
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
            ".env"
        )
        case_sensitive = True
        # 可选：如果你以后要在 .env 加别的变量但不想在这里写，可以解开下面这行
        # extra = "ignore" 

settings = Settings()