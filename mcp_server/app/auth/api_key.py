"""
API Key 验证模块
"""

import os
import logging
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def verify_api_key(authorization: Optional[str] = Security(api_key_header)) -> bool:
    """
    验证 API Key

    Args:
        authorization: Authorization header，通常格式为 "Bearer <api_key>"

    Returns:
        True if valid, raises HTTPException otherwise

    Raises:
        HTTPException: 401 if API key is invalid or missing
    """
    # 开发模式跳过认证
    if os.getenv("MCP_DEV_MODE", "false").lower() == "true":
        logger.debug("开发模式，跳过 API Key 验证")
        return True

    if not authorization:
        logger.warning("API Key 验证失败: 缺少 Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = authorization
    if authorization.startswith("Bearer "):
        api_key = authorization[7:]

    if not settings.validate_api_key(api_key):
        logger.warning(f"API Key 验证失败: 无效的 Key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


def extract_api_key(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization header 中提取 API Key"""
    if not authorization:
        return None

    if authorization.startswith("Bearer "):
        return authorization[7:]

    return authorization
