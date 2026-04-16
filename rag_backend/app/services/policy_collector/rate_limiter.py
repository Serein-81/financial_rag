"""
速率限制器
控制政策采集的请求频率，避免对目标网站造成压力
"""

import asyncio
import logging
import time
from typing import Dict, Optional
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    requests_per_second: float = 1.0
    requests_per_minute: int = 30
    requests_per_hour: int = 500
    burst_size: int = 5
    min_delay: float = 0.5


class RateLimiter:
    """
    多层速率限制器
    
    实现三层限流：
    1. 秒级限制（平滑限流）
    2. 分钟级限制
    3. 小时级限制
    
    支持令牌桶算法实现突发流量
    """
    
    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        self.default_config = default_config or RateLimitConfig()
        self._configs: Dict[str, RateLimitConfig] = {}
        
        self._request_times: Dict[str, list] = defaultdict(list)
        self._minute_requests: Dict[str, list] = defaultdict(list)
        self._hour_requests: Dict[str, list] = defaultdict(list)
        
        self._tokens: Dict[str, float] = defaultdict(lambda: self.default_config.burst_size)
        self._last_refill: Dict[str, float] = defaultdict(time.time)
        
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    def set_config(self, domain: str, config: RateLimitConfig):
        """
        设置特定域名的限流配置
        
        Args:
            domain: 域名
            config: 限流配置
        """
        self._configs[domain] = config
        logger.info(f"⚙️ [{domain}] 速率限制已配置: {config.requests_per_minute}次/分钟")
    
    async def acquire(self, domain: str) -> bool:
        """
        获取请求许可
        
        Args:
            domain: 目标域名
            
        Returns:
            bool: 是否获得许可
        """
        config = self._configs.get(domain, self.default_config)
        lock = self._locks[domain]
        
        async with lock:
            now = time.time()
            
            self._cleanup_old_requests(domain, now)
            
            if not self._check_limits(domain, config, now):
                wait_time = self._calculate_wait_time(domain, config, now)
                if wait_time > 0:
                    logger.warning(f"⏳ [{domain}] 速率限制触发，等待 {wait_time:.2f} 秒")
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    self._cleanup_old_requests(domain, now)
            
            if self._check_limits(domain, config, now):
                self._record_request(domain, now)
                self._refill_tokens(domain, config, now)
                return True
            
            return False
    
    def _cleanup_old_requests(self, domain: str, now: float):
        """清理过期的请求记录"""
        second_ago = now - 1
        minute_ago = now - 60
        hour_ago = now - 3600
        
        self._request_times[domain] = [
            t for t in self._request_times[domain] if t > second_ago
        ]
        
        self._minute_requests[domain] = [
            t for t in self._minute_requests[domain] if t > minute_ago
        ]
        
        self._hour_requests[domain] = [
            t for t in self._hour_requests[domain] if t > hour_ago
        ]
    
    def _check_limits(
        self,
        domain: str,
        config: RateLimitConfig,
        now: float
    ) -> bool:
        """
        检查是否满足所有限制
        
        Args:
            domain: 域名
            config: 限流配置
            now: 当前时间
            
        Returns:
            bool: 是否满足限制
        """
        recent_requests = len(self._request_times[domain])
        if recent_requests >= config.requests_per_second:
            return False
        
        recent_minute = len(self._minute_requests[domain])
        if recent_minute >= config.requests_per_minute:
            return False
        
        recent_hour = len(self._hour_requests[domain])
        if recent_hour >= config.requests_per_hour:
            return False
        
        if config.burst_size > 0:
            if self._tokens[domain] < 1:
                return False
        
        return True
    
    def _calculate_wait_time(
        self,
        domain: str,
        config: RateLimitConfig,
        now: float
    ) -> float:
        """
        计算需要等待的时间
        
        Args:
            domain: 域名
            config: 限流配置
            now: 当前时间
            
        Returns:
            float: 等待时间（秒）
        """
        wait_times = []
        
        if self._request_times[domain]:
            oldest_second = min(self._request_times[domain])
            time_since_oldest = now - oldest_second
            if time_since_oldest < 1:
                wait_times.append(1 - time_since_oldest)
        
        if self._minute_requests[domain]:
            oldest_minute = min(self._minute_requests[domain])
            time_since_oldest = now - oldest_minute
            if time_since_oldest < 60:
                wait_times.append(60 - time_since_oldest)
        
        if self._hour_requests[domain]:
            oldest_hour = min(self._hour_requests[domain])
            time_since_oldest = now - oldest_hour
            if time_since_oldest < 3600:
                wait_times.append(3600 - time_since_oldest)
        
        return max(wait_times) if wait_times else config.min_delay
    
    def _record_request(self, domain: str, now: float):
        """记录请求"""
        self._request_times[domain].append(now)
        self._minute_requests[domain].append(now)
        self._hour_requests[domain].append(now)
    
    def _refill_tokens(self, domain: str, config: RateLimitConfig, now: float):
        """补充令牌"""
        time_passed = now - self._last_refill[domain]
        refill_rate = config.requests_per_second
        
        self._tokens[domain] = min(
            config.burst_size,
            self._tokens[domain] + time_passed * refill_rate
        )
        self._last_refill[domain] = now
        
        if self._tokens[domain] >= 1:
            self._tokens[domain] -= 1
    
    def get_stats(self, domain: str) -> Dict:
        """
        获取域名限流统计
        
        Args:
            domain: 域名
            
        Returns:
            Dict: 统计信息
        """
        config = self._configs.get(domain, self.default_config)
        now = time.time()
        
        return {
            "domain": domain,
            "requests_last_second": len(self._request_times[domain]),
            "requests_last_minute": len(self._minute_requests[domain]),
            "requests_last_hour": len(self._hour_requests[domain]),
            "available_tokens": self._tokens[domain],
            "limit_per_second": config.requests_per_second,
            "limit_per_minute": config.requests_per_minute,
            "limit_per_hour": config.requests_per_hour,
            "burst_size": config.burst_size
        }
    
    def reset(self, domain: Optional[str] = None):
        """
        重置限流器
        
        Args:
            domain: 域名（None 表示重置所有）
        """
        if domain:
            self._request_times[domain].clear()
            self._minute_requests[domain].clear()
            self._hour_requests[domain].clear()
            self._tokens[domain] = self.default_config.burst_size
            logger.info(f"🔄 [{domain}] 速率限制已重置")
        else:
            self._request_times.clear()
            self._minute_requests.clear()
            self._hour_requests.clear()
            self._tokens.clear()
            logger.info("🔄 所有速率限制已重置")


rate_limiter = RateLimiter()


OFFICIAL_SOURCES_RATE_LIMITS = {
    "chinatax.gov.cn": RateLimitConfig(
        requests_per_second=0.5,
        requests_per_minute=20,
        requests_per_hour=200,
        burst_size=3
    ),
    "mof.gov.cn": RateLimitConfig(
        requests_per_second=0.5,
        requests_per_minute=20,
        requests_per_hour=200,
        burst_size=3
    ),
    "gov.cn": RateLimitConfig(
        requests_per_second=1.0,
        requests_per_minute=30,
        requests_per_hour=500,
        burst_size=5
    ),
}


for domain, config in OFFICIAL_SOURCES_RATE_LIMITS.items():
    rate_limiter.set_config(domain, config)
