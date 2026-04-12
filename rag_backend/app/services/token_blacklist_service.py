# app/services/token_blacklist_service.py

"""
JWT Token 黑名单服务

用于管理已撤销的 JWT Token，支持登出功能和 Token 撤销
"""

import uuid
import time
from typing import Optional, Dict, Any
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import settings
from app.core.exceptions import CacheException
import logging

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """
    Token 黑名单服务
    
    使用 Redis 存储已撤销的 Token，支持：
    - Token 撤销（添加到黑名单）
    - Token 黑名单检查
    - 自动过期清理
    """
    
    BLACKLIST_PREFIX = "token:blacklist:"
    
    def __init__(self):
        """初始化 Redis 连接"""
        self._redis_client: Optional[Redis] = None
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._init_redis()
    
    def _init_redis(self) -> None:
        """初始化 Redis 连接"""
        try:
            self._redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self._redis_client.ping()
            logger.info("✅ TokenBlacklist Redis连接成功")
        except RedisError as e:
            logger.warning(f"⚠️ TokenBlacklist Redis连接失败: {e}，使用内存存储")
            self._redis_client = None
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ TokenBlacklist 初始化数据错误: {e}，使用内存存储")
            self._redis_client = None
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ TokenBlacklist 初始化IO错误: {e}，使用内存存储")
            self._redis_client = None
        except Exception as e:
            logger.warning(f"⚠️ TokenBlacklist 初始化异常: {e}，使用内存存储")
            self._redis_client = None
    
    def _clean_expired_tokens(self) -> None:
        """清理过期的内存存储条目"""
        current_time = time.time()
        expired_keys = [
            jti for jti, data in self._memory_store.items()
            if data.get("expire_at", 0) < current_time
        ]
        for jti in expired_keys:
            del self._memory_store[jti]
    
    def add_to_blacklist(self, jti: str, expire_seconds: int) -> bool:
        """
        将 Token 添加到黑名单
        
        Args:
            jti: JWT Token ID
            expire_seconds: 过期时间（秒），应与 Token 剩余有效期一致
            
        Returns:
            是否添加成功
        """
        if not jti:
            logger.warning("⚠️ 尝试添加空的 JTI 到黑名单")
            return False
        
        try:
            if self._redis_client:
                key = f"{self.BLACKLIST_PREFIX}{jti}"
                self._redis_client.setex(key, expire_seconds, "revoked")
                logger.info(f"✅ Token已添加到黑名单 (Redis): jti={jti[:16]}..., expires_in={expire_seconds}s")
                return True
            else:
                self._memory_store[jti] = {
                    "revoked_at": time.time(),
                    "expire_at": time.time() + expire_seconds
                }
                self._clean_expired_tokens()
                logger.info(f"✅ Token已添加到黑名单 (Memory): jti={jti[:16]}..., expires_in={expire_seconds}s")
                return True
        except RedisError as e:
            logger.error(f"❌ Redis添加Token到黑名单失败: {e}")
            raise CacheException(
                message=f"Token黑名单添加失败: {str(e)}",
                operation="add_to_blacklist",
                original_error=str(e)
            )
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Token添加到黑名单数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ Token添加到黑名单IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Token添加到黑名单失败: {e}")
            return False
    
    def is_blacklisted(self, jti: str) -> bool:
        """
        检查 Token 是否在黑名单中
        
        Args:
            jti: JWT Token ID
            
        Returns:
            是否在黑名单中
        """
        if not jti:
            return False
        
        try:
            if self._redis_client:
                key = f"{self.BLACKLIST_PREFIX}{jti}"
                return self._redis_client.exists(key) > 0
            else:
                if jti in self._memory_store:
                    data = self._memory_store[jti]
                    if data.get("expire_at", 0) < time.time():
                        del self._memory_store[jti]
                        return False
                    return True
                return False
        except RedisError as e:
            logger.error(f"❌ Redis检查Token黑名单失败: {e}")
            raise CacheException(
                message=f"Token黑名单检查失败: {str(e)}",
                operation="is_blacklisted",
                original_error=str(e)
            )
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 检查Token黑名单数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 检查Token黑名单IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 检查Token黑名单失败: {e}")
            return False
    
    def remove_from_blacklist(self, jti: str) -> bool:
        """
        从黑名单中移除 Token（通常不需要，依赖自动过期）
        
        Args:
            jti: JWT Token ID
            
        Returns:
            是否移除成功
        """
        if not jti:
            return False
        
        try:
            if self._redis_client:
                key = f"{self.BLACKLIST_PREFIX}{jti}"
                result = self._redis_client.delete(key) > 0
                if result:
                    logger.info(f"✅ Token已从黑名单移除 (Redis): jti={jti[:16]}...")
                return result
            else:
                if jti in self._memory_store:
                    del self._memory_store[jti]
                    logger.info(f"✅ Token已从黑名单移除 (Memory): jti={jti[:16]}...")
                    return True
                return False
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 从黑名单移除Token数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"❌ 从黑名单移除Token IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 从黑名单移除Token失败: {e}")
            return False
    
    def get_blacklist_count(self) -> int:
        """
        获取黑名单中的 Token 数量
        
        Returns:
            黑名单中的 Token 数量
        """
        try:
            if self._redis_client:
                count = 0
                cursor = 0
                pattern = f"{self.BLACKLIST_PREFIX}*"
                while True:
                    cursor, keys = self._redis_client.scan(cursor, match=pattern, count=100)
                    count += len(keys)
                    if cursor == 0:
                        break
                return count
            else:
                self._clean_expired_tokens()
                return len(self._memory_store)
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 获取黑名单数量数据错误: {e}")
            return 0
        except (OSError, IOError) as e:
            logger.error(f"❌ 获取黑名单数量IO错误: {e}")
            return 0
        except Exception as e:
            logger.error(f"❌ 获取黑名单数量失败: {e}")
            return 0


token_blacklist_service = TokenBlacklistService()
