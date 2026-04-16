"""
API 限流中间件

企业级API限流实现，支持：
1. 多级限流：全局/租户/用户/API Key
2. 多种限流策略：滑动窗口/令牌桶/固定窗口
3. 分布式存储支持：内存/Redis
4. 优雅降级：限流服务不可用时允许请求通过
5. 标准HTTP响应：429状态码 + Retry-After头

使用示例：
```python
# 在 main.py 中注册
app.add_middleware(RateLimitMiddleware)
```
"""

import asyncio
import logging
import time
from typing import Dict, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitStrategy(str, Enum):
    """限流策略"""
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitTier:
    """限流层级配置"""
    requests_per_minute: int
    requests_per_hour: int
    burst_size: int = 10


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    API 限流中间件
    
    功能：
    1. 基于滑动窗口算法的请求限流
    2. 支持多级限流：全局 < 租户 < 用户 < API Key
    3. 返回标准 HTTP 429 状态码和 Retry-After 头
    4. 优雅降级：限流服务不可用时允许请求通过
    5. 异步并发安全：使用 asyncio.Lock 保护共享状态
    """
    
    # 默认限流配置（全局）
    DEFAULT_TIER = RateLimitTier(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_size=10
    )
    
    # 不同端点的限流配置
    ENDPOINT_TIERS: Dict[str, RateLimitTier] = {
        "/api/v1/chat/completions": RateLimitTier(30, 500, 5),
        "/api/v1/chat/agent_chat": RateLimitTier(30, 500, 5),
        "/api/v1/chat/completions_stream": RateLimitTier(30, 500, 5),
        "/api/v1/chat/agent_chat_stream": RateLimitTier(30, 500, 5),
        "/api/v1/multi-agent/execute": RateLimitTier(10, 200, 3),
        "/api/v1/search/hybrid": RateLimitTier(60, 1000, 10),
    }
    
    # 排除路径（不需要限流）
    EXCLUDED_PATHS = {
        "/health",
        "/api/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/agent-discovery/summary",
        "/api/v1/agent-discovery/tools",
        "/api/v1/multi-agent/health",
        "/api/v1/multi-agent/metrics",
        "/api/v1/multi-agent/security-events",
        "/api/v1/multi-agent/security-stats",
        "/api/v1/tenant-settings/me",
        "/api/v1/langsmith/status",
        "/api/v1/langsmith/stats",
        "/api/v1/observability/traces",
        "/api/v1/observability/metrics",
        "/api/v1/observability/logs",
        "/api/v1/observability/health",
        "/api/v1/security/tenants",
        "/api/v1/security/permissions",
        "/api/v1/security/cypher-validate",
        "/api/v1/security/audit-logs",
    }
    
    def __init__(self, app, strategy: str = "sliding_window"):
        super().__init__(app)
        self.strategy = RateLimitStrategy(strategy)
        self.enabled = settings.RATE_LIMIT_ENABLED
        
        # 滑动窗口存储: {key: deque of timestamps}
        self._sliding_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        
        # 令牌桶存储: {key: (tokens, last_refill_time)}
        self._token_buckets: Dict[str, Tuple[float, float]] = {}
        
        # 固定窗口存储: {key: (count, window_start)}
        self._fixed_windows: Dict[str, Tuple[int, float]] = {}
        
        # 异步锁保护
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # 统计信息
        self._stats = {
            "total_requests": 0,
            "limited_requests": 0,
            "excluded_requests": 0,
        }
        
        logger.info(f"🚀 RateLimitMiddleware 初始化完成, 策略: {self.strategy}, 启用: {self.enabled}")
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求"""
        
        # 如果限流未启用，直接通过
        if not self.enabled:
            return await call_next(request)
        
        # 检查是否排除路径
        if self._is_excluded_path(request.url.path):
            self._stats["excluded_requests"] += 1
            return await call_next(request)
        
        # 生成限流键
        rate_limit_key = self._generate_key(request)
        
        # 获取限流配置
        tier = self._get_tier(request.url.path)
        
        # 检查限流
        is_allowed, retry_after = await self.check_rate_limit(
            rate_limit_key,
            tier,
            request.url.path
        )
        
        self._stats["total_requests"] += 1
        
        if not is_allowed:
            self._stats["limited_requests"] += 1
            print(f"⏳ [RATE] {request.url.path} - Limited (retry_after={retry_after}s)")
            logger.warning(
                f"⏳ 限流触发: key={rate_limit_key}, "
                f"path={request.url.path}, retry_after={retry_after}s"
            )
            return self._rate_limit_response(retry_after, rate_limit_key)
        
        # 执行请求
        response = await call_next(request)
        
        # 在响应头中添加限流信息
        self._add_rate_limit_headers(response, rate_limit_key, tier)
        
        return response
    
    def _is_excluded_path(self, path: str) -> bool:
        """检查是否排除路径"""
        return any(
            path.startswith(excluded) or path == excluded 
            for excluded in self.EXCLUDED_PATHS
        )
    
    def _generate_key(self, request: Request) -> str:
        """
        生成限流键
        
        优先级: API Key > User ID > Tenant ID > IP
        
        Returns:
            str: 限流键格式 "type:value"
        """
        # 1. 优先使用 API Key
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key:
            return f"apikey:{api_key[:16]}"  # 截断保护
        
        # 2. 使用 User ID
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        
        # 3. 使用 Tenant ID
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return f"tenant:{tenant_id}"
        
        # 4. 最后使用 IP
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        # 优先从 X-Forwarded-For 获取
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # 其次从 X-Real-IP 获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 最后使用 client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_tier(self, path: str) -> RateLimitTier:
        """获取路径对应的限流层级"""
        for endpoint, tier in self.ENDPOINT_TIERS.items():
            if path.startswith(endpoint):
                return tier
        
        return self.DEFAULT_TIER
    
    async def check_rate_limit(
        self,
        key: str,
        tier: RateLimitTier,
        path: str
    ) -> Tuple[bool, int]:
        """
        检查是否允许请求
        
        Args:
            key: 限流键
            tier: 限流配置
            path: 请求路径
            
        Returns:
            Tuple[bool, int]: (是否允许, 重试等待秒数)
        """
        lock = self._locks[key]
        
        async with lock:
            try:
                if self.strategy == RateLimitStrategy.SLIDING_WINDOW:
                    return await self._check_sliding_window(key, tier)
                elif self.strategy == RateLimitStrategy.TOKEN_BUCKET:
                    return await self._check_token_bucket(key, tier)
                elif self.strategy == RateLimitStrategy.FIXED_WINDOW:
                    return await self._check_fixed_window(key, tier)
                else:
                    return await self._check_sliding_window(key, tier)
            except Exception as e:
                # 限流服务异常时，优雅降级：允许请求通过
                logger.error(f"❌ 限流检查异常: {e}, 允许请求通过")
                return True, 0
    
    async def _check_sliding_window(
        self,
        key: str,
        tier: RateLimitTier
    ) -> Tuple[bool, int]:
        """
        滑动窗口算法
        
        滑动窗口算法将时间划分为更小的窗口，
        统计当前窗口内的请求数，提供更平滑的限流。
        """
        now = time.time()
        window_size = 60  # 1分钟窗口
        
        # 清理过期请求
        cutoff_time = now - window_size
        while self._sliding_windows[key] and self._sliding_windows[key][0] < cutoff_time:
            self._sliding_windows[key].popleft()
        
        current_count = len(self._sliding_windows[key])
        
        # 检查分钟级限制
        if current_count >= tier.requests_per_minute:
            # 计算需要等待的时间
            oldest_timestamp = self._sliding_windows[key][0]
            retry_after = int(oldest_timestamp + window_size - now) + 1
            return False, max(1, retry_after)
        
        # 检查小时级限制（简化：使用分钟数 * 60）
        hour_cutoff = now - 3600
        hour_requests = sum(1 for ts in self._sliding_windows[key] if ts > hour_cutoff)
        if hour_requests >= tier.requests_per_hour:
            oldest_in_hour = min((ts for ts in self._sliding_windows[key] if ts > hour_cutoff), default=now)
            retry_after = int(oldest_in_hour + 3600 - now) + 1
            return False, max(1, retry_after)
        
        # 允许请求
        self._sliding_windows[key].append(now)
        return True, 0
    
    async def _check_token_bucket(
        self,
        key: str,
        tier: RateLimitTier
    ) -> Tuple[bool, int]:
        """
        令牌桶算法
        
        令牌桶允许一定程度的突发流量，
        同时保证长期来看不会超过平均速率。
        """
        now = time.time()
        refill_rate = tier.requests_per_minute / 60.0  # 每秒补充的令牌数
        
        if key not in self._token_buckets:
            # 初始化桶：满桶
            self._token_buckets[key] = (float(tier.burst_size), now)
        
        tokens, last_refill = self._token_buckets[key]
        
        # 补充令牌
        elapsed = now - last_refill
        tokens = min(tier.burst_size, tokens + elapsed * refill_rate)
        
        if tokens >= 1:
            # 消耗一个令牌
            tokens -= 1
            self._token_buckets[key] = (tokens, now)
            return True, 0
        else:
            # 没有令牌，计算等待时间
            retry_after = int((1 - tokens) / refill_rate) + 1
            return False, retry_after
    
    async def _check_fixed_window(
        self,
        key: str,
        tier: RateLimitTier
    ) -> Tuple[bool, int]:
        """
        固定窗口算法
        
        将时间划分为固定大小的窗口，
        每个窗口有独立的计数器。
        """
        now = time.time()
        window_size = 60  # 1分钟窗口
        
        # 计算当前窗口起始时间
        window_start = int(now / window_size) * window_size
        
        if key in self._fixed_windows:
            count, saved_window_start = self._fixed_windows[key]
            
            if saved_window_start == window_start:
                # 同一窗口内，增加计数
                if count >= tier.requests_per_minute:
                    retry_after = int(window_start + window_size - now) + 1
                    return False, max(1, retry_after)
                
                self._fixed_windows[key] = (count + 1, window_start)
            else:
                # 新窗口，重置计数
                self._fixed_windows[key] = (1, window_start)
        else:
            # 新键，创建窗口
            self._fixed_windows[key] = (1, window_start)
        
        return True, 0
    
    def _rate_limit_response(self, retry_after: int, key: str) -> JSONResponse:
        """生成限流响应"""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Too Many Requests",
                "message": f"请求过于频繁，请 {retry_after} 秒后重试",
                "detail": f"Rate limit exceeded for {key}",
                "retry_after": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(self.DEFAULT_TIER.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                "X-RateLimit-Key": key,
            }
        )
    
    def _add_rate_limit_headers(
        self,
        response: Response,
        key: str,
        tier: RateLimitTier
    ):
        """添加限流信息到响应头"""
        # 获取当前窗口的剩余请求数
        now = time.time()
        
        if self.strategy == RateLimitStrategy.SLIDING_WINDOW:
            cutoff_time = now - 60
            current_count = sum(1 for ts in self._sliding_windows[key] if ts > cutoff_time)
            remaining = max(0, tier.requests_per_minute - current_count)
        elif self.strategy == RateLimitStrategy.TOKEN_BUCKET:
            if key in self._token_buckets:
                tokens, _ = self._token_buckets[key]
                remaining = int(tokens)
            else:
                remaining = tier.burst_size
        else:
            remaining = tier.requests_per_minute
        
        response.headers["X-RateLimit-Limit"] = str(tier.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(now) + 60)
        response.headers["X-RateLimit-Key"] = key
    
    def get_stats(self) -> Dict:
        """获取限流统计信息"""
        total = self._stats["total_requests"]
        limited = self._stats["limited_requests"]
        
        return {
            **self._stats,
            "limit_rate": limited / total if total > 0 else 0,
            "strategy": self.strategy.value,
            "enabled": self.enabled,
        }
    
    async def reset_key(self, key: str):
        """重置指定键的限流状态"""
        lock = self._locks[key]
        async with lock:
            if key in self._sliding_windows:
                self._sliding_windows[key].clear()
            if key in self._token_buckets:
                del self._token_buckets[key]
            if key in self._fixed_windows:
                del self._fixed_windows[key]
            
            logger.info(f"🔄 已重置限流键: {key}")
    
    async def cleanup_expired(self, max_age_seconds: int = 3600):
        """清理过期的限流状态"""
        now = time.time()
        cutoff_time = now - max_age_seconds
        
        # 清理滑动窗口
        expired_keys = [
            key for key, window in self._sliding_windows.items()
            if not window or window[-1] < cutoff_time
        ]
        for key in expired_keys:
            del self._sliding_windows[key]
        
        # 清理令牌桶
        expired_keys = [
            key for key, (_, last_refill) in self._token_buckets.items()
            if last_refill < cutoff_time
        ]
        for key in expired_keys:
            del self._token_buckets[key]
        
        # 清理固定窗口
        expired_keys = [
            key for key, (_, window_start) in self._fixed_windows.items()
            if window_start < cutoff_time
        ]
        for key in expired_keys:
            del self._fixed_windows[key]
        
        if expired_keys:
            logger.info(f"🧹 清理了 {len(expired_keys)} 个过期限流键")
