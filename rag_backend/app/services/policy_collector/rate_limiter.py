"""
速率限制器
控制政策采集的请求频率，避免对目标网站造成压力

合规要求：
1. 遵守 robots.txt 中的 Crawl-Delay
2. 不超过官方网站的承受能力
3. 支持自适应限流
4. 记录所有限流事件
"""

import asyncio
import logging
import time
from typing import Dict, Optional, List
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    requests_per_second: float = 1.0
    requests_per_minute: int = 30
    requests_per_hour: int = 500
    burst_size: int = 5
    min_delay: float = 0.5
    respect_robots_delay: bool = True


@dataclass
class RateLimitEvent:
    """限流事件记录"""
    timestamp: datetime
    domain: str
    event_type: str
    waited_seconds: float = 0.0
    reason: str = ""


class RateLimiter:
    """
    多层速率限制器
    
    实现三层限流：
    1. 秒级限制（平滑限流）
    2. 分钟级限制
    3. 小时级限制
    
    支持：
    - 令牌桶算法实现突发流量
    - 自适应限流（根据响应状态调整）
    - robots.txt Crawl-Delay 尊重
    - 限流事件审计日志
    """
    
    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        self.default_config = default_config or RateLimitConfig()
        self._configs: Dict[str, RateLimitConfig] = {}
        self._robots_delays: Dict[str, float] = {}
        
        self._request_times: Dict[str, list] = defaultdict(list)
        self._minute_requests: Dict[str, list] = defaultdict(list)
        self._hour_requests: Dict[str, list] = defaultdict(list)
        
        self._tokens: Dict[str, float] = defaultdict(lambda: self.default_config.burst_size)
        self._last_refill: Dict[str, float] = defaultdict(time.time)
        
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        self._rate_limit_events: List[RateLimitEvent] = []
        
        self._error_count: Dict[str, int] = defaultdict(int)
        self._success_count: Dict[str, int] = defaultdict(int)
    
    def set_robots_crawl_delay(self, domain: str, delay: float):
        """
        设置 robots.txt 指定的爬取延迟
        
        Args:
            domain: 域名
            delay: 延迟秒数
        """
        self._robots_delays[domain] = delay
        logger.info(f"⏱️ [{domain}] 设置 Crawl-Delay: {delay}秒")
    
    async def acquire(
        self, 
        domain: str,
        force: bool = False
    ) -> bool:
        """
        获取请求许可
        
        Args:
            domain: 目标域名
            force: 强制获取（跳过某些检查）
            
        Returns:
            bool: 是否获得许可
        """
        config = self._configs.get(domain, self.default_config)
        lock = self._locks[domain]
        
        async with lock:
            now = time.time()
            
            self._cleanup_old_requests(domain, now)
            
            if not force and not self._check_limits(domain, config, now):
                wait_time = self._calculate_wait_time(domain, config, now)
                if wait_time > 0:
                    logger.warning(f"⏳ [{domain}] 速率限制触发，等待 {wait_time:.2f} 秒")
                    self._log_event(domain, "rate_limit", wait_time, "多层限制触发")
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    self._cleanup_old_requests(domain, now)
            
            robots_delay = self._robots_delays.get(domain, 0)
            if robots_delay > 0 and config.respect_robots_delay:
                last_request = self._last_request_time.get(domain, 0)
                time_since_last = now - last_request
                if time_since_last < robots_delay:
                    wait = robots_delay - time_since_last
                    logger.info(f"⏱️ [{domain}] 尊重 Crawl-Delay: {wait:.2f}秒")
                    self._log_event(domain, "robots_delay", wait, f"Crawl-Delay: {robots_delay}s")
                    await asyncio.sleep(wait)
            
            if self._check_limits(domain, config, now):
                self._record_request(domain, now)
                self._refill_tokens(domain, config, now)
                self._last_request_time[domain] = time.time()
                return True
            
            return False
    
    def record_response_status(self, domain: str, status_code: int):
        """
        记录响应状态，用于自适应限流
        
        Args:
            domain: 域名
            status_code: HTTP 状态码
        """
        if status_code >= 500:
            self._error_count[domain] += 1
            if self._error_count[domain] >= 3:
                self._reduce_rate(domain)
                logger.warning(f"⚠️ [{domain}] 连续错误，降低请求速率")
        elif status_code == 200:
            self._success_count[domain] += 1
            self._error_count[domain] = 0
    
    def _reduce_rate(self, domain: str):
        """降低请求速率"""
        if domain in self._configs:
            config = self._configs[domain]
            config.requests_per_second *= 0.5
            config.requests_per_minute = int(config.requests_per_minute * 0.8)
            logger.info(f"📉 [{domain}] 速率降至: {config.requests_per_second}/秒")
    
    def _log_event(
        self, 
        domain: str, 
        event_type: str, 
        waited: float,
        reason: str
    ):
        """记录限流事件"""
        event = RateLimitEvent(
            timestamp=datetime.now(),
            domain=domain,
            event_type=event_type,
            waited_seconds=waited,
            reason=reason
        )
        self._rate_limit_events.append(event)
        if len(self._rate_limit_events) > 1000:
            self._rate_limit_events = self._rate_limit_events[-500:]
    
    def get_rate_limit_events(
        self, 
        domain: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取限流事件记录
        
        Args:
            domain: 域名过滤（None 表示所有）
            limit: 返回数量
            
        Returns:
            List[Dict]: 事件列表
        """
        events = self._rate_limit_events
        if domain:
            events = [e for e in events if e.domain == domain]
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "domain": e.domain,
                "event_type": e.event_type,
                "waited_seconds": e.waited_seconds,
                "reason": e.reason
            }
            for e in events[-limit:]
        ]
    
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
    "flfg.pan.gov.cn": RateLimitConfig(
        requests_per_second=1.0,
        requests_per_minute=30,
        requests_per_hour=500,
        burst_size=5,
        min_delay=1.0
    ),
    "www.gov.cn": RateLimitConfig(
        requests_per_second=1.0,
        requests_per_minute=30,
        requests_per_hour=500,
        burst_size=5,
        min_delay=1.0
    ),
    "chinatax.gov.cn": RateLimitConfig(
        requests_per_second=0.5,
        requests_per_minute=20,
        requests_per_hour=200,
        burst_size=3,
        min_delay=2.0
    ),
    "mof.gov.cn": RateLimitConfig(
        requests_per_second=0.5,
        requests_per_minute=20,
        requests_per_hour=200,
        burst_size=3,
        min_delay=2.0
    ),
    "www.mof.gov.cn": RateLimitConfig(
        requests_per_second=0.5,
        requests_per_minute=20,
        requests_per_hour=200,
        burst_size=3,
        min_delay=2.0
    ),
}


for domain, config in OFFICIAL_SOURCES_RATE_LIMITS.items():
    rate_limiter.set_config(domain, config)
