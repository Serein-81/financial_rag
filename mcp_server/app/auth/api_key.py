"""API key authentication helpers."""

import logging
import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def verify_api_key(authorization: Optional[str] = Security(api_key_header)) -> bool:
    """Validate the configured API key from an Authorization header."""
    if os.getenv("MCP_DEV_MODE", "false").lower() == "true":
        logger.debug("Development mode enabled; skipping API key validation")
        return True

    if not authorization:
        logger.warning("API key validation failed: missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = extract_api_key(authorization)

    if not api_key or not settings.validate_api_key(api_key):
        logger.warning("API key validation failed: invalid key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


def extract_api_key(authorization: Optional[str]) -> Optional[str]:
    """Extract a bearer token or raw API key from an Authorization header."""
    if not authorization:
        return None

    if authorization.startswith("Bearer "):
        return authorization[7:]

    return authorization
