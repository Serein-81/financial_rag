"""
MCP 服务器配置
"""

import os
from typing import List, Optional


class Settings:
    """服务器配置"""

    def __init__(self):
        self.host: str = os.getenv("MCP_HOST", "0.0.0.0")
        self.port: int = int(os.getenv("MCP_PORT", "5000"))
        self.debug: bool = os.getenv("MCP_DEBUG", "false").lower() == "true"

        self.api_keys: List[str] = self._parse_api_keys()

        self.cors_origins: List[str] = os.getenv(
            "MCP_CORS_ORIGINS", "*"
        ).split(",")

        self.log_level: str = os.getenv("MCP_LOG_LEVEL", "INFO")

        self.request_timeout: int = int(os.getenv("MCP_REQUEST_TIMEOUT", "120"))

        self.max_retries: int = int(os.getenv("MCP_MAX_RETRIES", "3"))

    def _parse_api_keys(self) -> List[str]:
        """解析 API Key 列表"""
        keys_str = os.getenv("MCP_API_KEYS", "")
        if not keys_str:
            return []
        return [k.strip() for k in keys_str.split(",") if k.strip()]

    def validate_api_key(self, api_key: str) -> bool:
        """验证 API Key 是否有效"""
        if not self.api_keys:
            return True
        return api_key in self.api_keys

    @property
    def api_keys_count(self) -> int:
        """已配置的 API Key 数量"""
        return len(self.api_keys)


settings = Settings()
