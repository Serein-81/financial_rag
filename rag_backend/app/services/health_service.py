"""
健康检查服务

提供系统各组件的健康检查功能：
1. 数据库健康检查
2. Redis健康检查
3. LLM服务健康检查
4. 存储服务健康检查
5. MCP服务健康检查
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """组件健康信息"""
    name: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    last_check: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "details": self.details,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }


@dataclass
class HealthReport:
    """健康报告"""
    overall_status: HealthStatus
    timestamp: datetime
    uptime_seconds: float
    components: List[ComponentHealth]
    summary: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.overall_status.value,
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "components": [c.to_dict() for c in self.components],
            "summary": self.summary,
        }


class HealthService:
    """
    健康检查服务
    
    功能：
    1. 数据库健康检查
    2. Redis健康检查
    3. LLM服务健康检查
    4. 存储服务健康检查
    5. MCP服务健康检查
    """
    
    # 检查超时（秒）
    CHECK_TIMEOUT = 5
    
    # 启动时间
    _start_time: datetime = field(default_factory=lambda: datetime.now())
    
    def __init__(self):
        self._last_check_time: Optional[datetime] = None
        self._cached_report: Optional[HealthReport] = None
        self._cache_ttl_seconds = 10  # 缓存TTL
        self._start_time = datetime.now()
        
        logger.info("🚀 HealthService 初始化完成")
    
    @property
    def uptime(self) -> float:
        """获取运行时间（秒）"""
        return (datetime.now() - self._start_time).total_seconds()
    
    async def check_database(self) -> ComponentHealth:
        """检查数据库健康"""
        start_time = time.time()
        
        try:
            from app.db.session import engine
            from sqlalchemy import text
            
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            latency = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                message="Database connection successful",
                last_check=datetime.now()
            )
            
        except (ValueError, KeyError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 数据库健康检查数据错误: {e}")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"数据库健康检查数据错误: {str(e)}",
                last_check=datetime.now()
            )
        except (OSError, IOError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 数据库健康检查IO错误: {e}")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"数据库健康检查IO错误: {str(e)}",
                last_check=datetime.now()
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 数据库健康检查失败: {e}")
            
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"Database connection failed: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_redis(self) -> ComponentHealth:
        """检查Redis健康"""
        start_time = time.time()
        
        try:
            from app.services.redis_service import get_redis_service
            
            redis_service = await get_redis_service()
            result = await redis_service.redis.set("health_check", "ok", ex=10)
            
            if result:
                latency = (time.time() - start_time) * 1000
                
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(latency, 2),
                    message="Redis connection successful",
                    last_check=datetime.now()
                )
            else:
                latency = (time.time() - start_time) * 1000
                
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    latency_ms=round(latency, 2),
                    message="Redis connection unstable",
                    last_check=datetime.now()
                )
                
        except (ValueError, KeyError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ Redis健康检查数据错误: {e}")
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"Redis健康检查数据错误: {str(e)}",
                last_check=datetime.now()
            )
        except (OSError, IOError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ Redis健康检查IO错误: {e}")
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"Redis健康检查IO错误: {str(e)}",
                last_check=datetime.now()
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ Redis健康检查失败: {e}")
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"Redis connection failed: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_llm_service(self) -> ComponentHealth:
        """检查LLM服务健康"""
        start_time = time.time()
        
        try:
            from app.services.llm_service import llm_service
            
            # 简单的健康检查调用
            result = await asyncio.wait_for(
                llm_service.check_health(),
                timeout=self.CHECK_TIMEOUT
            )
            
            latency = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.HEALTHY if result else HealthStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message="LLM service healthy" if result else "LLM service returned empty response",
                details={"response_received": result},
                last_check=datetime.now()
            )
            
        except asyncio.TimeoutError:
            latency = (time.time() - start_time) * 1000
            logger.warning("⏱️ LLM服务健康检查超时")
            
            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message="LLM service timeout",
                last_check=datetime.now()
            )
            
        except (ValueError, KeyError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ LLM服务健康检查数据错误: {e}")
            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"LLM服务健康检查数据错误: {str(e)}",
                last_check=datetime.now()
            )
        except (OSError, IOError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ LLM服务健康检查IO错误: {e}")
            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"LLM服务健康检查IO错误: {str(e)}",
                last_check=datetime.now()
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ LLM服务健康检查失败: {e}")

            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"LLM service error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_storage(self) -> ComponentHealth:
        """检查存储服务健康"""
        start_time = time.time()
        
        try:
            from app.services.minio_service import minio_service
            
            # 检查MinIO连接
            await asyncio.wait_for(
                minio_service.health_check(),
                timeout=self.CHECK_TIMEOUT
            )
            
            latency = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="storage",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                message="Storage service healthy",
                last_check=datetime.now()
            )
            
        except asyncio.TimeoutError:
            latency = (time.time() - start_time) * 1000
            logger.warning("⏱️ 存储服务健康检查超时")
            
            return ComponentHealth(
                name="storage",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message="Storage service timeout",
                last_check=datetime.now()
            )
            
        except (ValueError, KeyError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 存储服务健康检查数据错误: {e}")
            return ComponentHealth(
                name="storage",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"存储服务健康检查数据错误: {str(e)}",
                last_check=datetime.now()
            )
        except (OSError, IOError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 存储服务健康检查IO错误: {e}")
            return ComponentHealth(
                name="storage",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"存储服务健康检查IO错误: {str(e)}",
                last_check=datetime.now()
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 存储服务健康检查失败: {e}")
            
            return ComponentHealth(
                name="storage",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"Storage service error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_vector_store(self) -> ComponentHealth:
        """检查向量存储健康"""
        start_time = time.time()
        
        try:
            from app.services.search_service import search_service
            
            # 检查向量数据库
            result = await asyncio.wait_for(
                search_service.check_health(),
                timeout=self.CHECK_TIMEOUT
            )
            
            latency = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="vector_store",
                status=HealthStatus.HEALTHY if result else HealthStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message="Vector store healthy" if result else "Vector store check returned false",
                last_check=datetime.now()
            )
            
        except asyncio.TimeoutError:
            latency = (time.time() - start_time) * 1000
            logger.warning("⏱️ 向量存储健康检查超时")
            
            return ComponentHealth(
                name="vector_store",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message="Vector store timeout",
                last_check=datetime.now()
            )
            
        except (ValueError, KeyError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 向量存储健康检查数据错误: {e}")
            return ComponentHealth(
                name="vector_store",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"向量存储健康检查数据错误: {str(e)}",
                last_check=datetime.now()
            )
        except (OSError, IOError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 向量存储健康检查IO错误: {e}")
            return ComponentHealth(
                name="vector_store",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"向量存储健康检查IO错误: {str(e)}",
                last_check=datetime.now()
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 向量存储健康检查失败: {e}")
            
            return ComponentHealth(
                name="vector_store",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=f"Vector store error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_mcp_services(self) -> ComponentHealth:
        """检查MCP服务健康"""
        start_time = time.time()
        
        try:
            from app.mcp.client_manager import client_manager
            
            # 检查MCP客户端管理器
            mcp_health = await asyncio.wait_for(
                client_manager.health_check(),
                timeout=self.CHECK_TIMEOUT
            )
            
            latency = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="mcp_services",
                status=HealthStatus.HEALTHY if mcp_health else HealthStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message="MCP services healthy" if mcp_health else "Some MCP services unhealthy",
                details=mcp_health if isinstance(mcp_health, dict) else None,
                last_check=datetime.now()
            )
            
        except asyncio.TimeoutError:
            latency = (time.time() - start_time) * 1000
            logger.warning("⏱️ MCP服务健康检查超时")
            
            return ComponentHealth(
                name="mcp_services",
                status=HealthStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message="MCP services timeout",
                last_check=datetime.now()
            )
            
        except (ValueError, KeyError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ MCP服务健康检查数据错误: {e}")
            return ComponentHealth(
                name="mcp_services",
                status=HealthStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message=f"MCP服务健康检查数据错误: {str(e)}",
                last_check=datetime.now()
            )
        except (OSError, IOError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ MCP服务健康检查IO错误: {e}")
            return ComponentHealth(
                name="mcp_services",
                status=HealthStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message=f"MCP服务健康检查IO错误: {str(e)}",
                last_check=datetime.now()
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ MCP服务健康检查失败: {e}")
            
            return ComponentHealth(
                name="mcp_services",
                status=HealthStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message=f"MCP services error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_rate_limiter(self) -> ComponentHealth:
        """检查限流器健康"""
        start_time = time.time()
        
        try:
            from app.middleware.rate_limit_middleware import RateLimitMiddleware
            from app.main import app
            
            # 查找限流中间件
            rate_limiter = None
            for handler in app.middleware_stack._middleware:
                if isinstance(handler, RateLimitMiddleware):
                    rate_limiter = handler
                    break
            
            latency = (time.time() - start_time) * 1000
            
            if rate_limiter:
                stats = rate_limiter.get_stats()
                
                return ComponentHealth(
                    name="rate_limiter",
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(latency, 2),
                    message="Rate limiter healthy",
                    details={
                        "total_requests": stats.get("total_requests"),
                        "limited_requests": stats.get("limited_requests"),
                        "limit_rate": stats.get("limit_rate"),
                    },
                    last_check=datetime.now()
                )
            else:
                return ComponentHealth(
                    name="rate_limiter",
                    status=HealthStatus.UNKNOWN,
                    latency_ms=round(latency, 2),
                    message="Rate limiter not initialized",
                    last_check=datetime.now()
                )
                
        except (ValueError, KeyError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 限流器健康检查数据错误: {e}")
            return ComponentHealth(
                name="rate_limiter",
                status=HealthStatus.UNKNOWN,
                latency_ms=round(latency, 2),
                message=f"限流器健康检查数据错误: {str(e)}",
                last_check=datetime.now()
            )
        except (OSError, IOError) as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 限流器健康检查IO错误: {e}")
            return ComponentHealth(
                name="rate_limiter",
                status=HealthStatus.UNKNOWN,
                latency_ms=round(latency, 2),
                message=f"限流器健康检查IO错误: {str(e)}",
                last_check=datetime.now()
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"❌ 限流器健康检查失败: {e}")
            
            return ComponentHealth(
                name="rate_limiter",
                status=HealthStatus.UNKNOWN,
                latency_ms=round(latency, 2),
                message=f"Rate limiter check error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_all(
        self,
        use_cache: bool = True,
        components: Optional[List[str]] = None
    ) -> HealthReport:
        """
        检查所有组件健康
        
        Args:
            use_cache: 是否使用缓存
            components: 要检查的组件列表，None表示检查所有
            
        Returns:
            HealthReport: 健康报告
        """
        # 检查缓存
        if use_cache and self._cached_report:
            cache_age = (datetime.now() - self._cached_report.timestamp).total_seconds()
            if cache_age < self._cache_ttl_seconds:
                return self._cached_report
        
        # 定义所有检查项
        all_checks = {
            "database": self.check_database,
            "redis": self.check_redis,
            "llm_service": self.check_llm_service,
            "storage": self.check_storage,
            "vector_store": self.check_vector_store,
            "mcp_services": self.check_mcp_services,
            "rate_limiter": self.check_rate_limiter,
        }
        
        # 确定要执行的检查
        checks_to_run = all_checks
        if components:
            checks_to_run = {k: v for k, v in all_checks.items() if k in components}
        
        # 并行执行检查
        tasks = [check() for check in checks_to_run.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        components_health = []
        summary = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0,
        }
        
        for check_name, result in zip(checks_to_run.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"❌ {check_name} 健康检查异常: {result}")
                health = ComponentHealth(
                    name=check_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check exception: {str(result)}",
                    last_check=datetime.now()
                )
            else:
                health = result
            
            components_health.append(health)
            summary[health.status.value] += 1
        
        # 确定总体状态
        if summary["unhealthy"] > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif summary["degraded"] > 0:
            overall_status = HealthStatus.DEGRADED
        elif summary["unknown"] > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # 创建报告
        report = HealthReport(
            overall_status=overall_status,
            timestamp=datetime.now(),
            uptime_seconds=self.uptime,
            components=components_health,
            summary=summary
        )
        
        # 更新缓存
        self._cached_report = report
        self._last_check_time = datetime.now()
        
        return report
    
    async def check_simple(self) -> Dict[str, Any]:
        """
        简单健康检查（快速）
        
        Returns:
            Dict: 健康状态字典
        """
        return await self.check_all(use_cache=False)
    
    async def check_quick(self) -> Dict[str, Any]:
        """
        快速健康检查（只检查关键组件）
        
        Returns:
            Dict: 健康状态字典
        """
        report = await self.check_all(
            use_cache=True,
            components=["database", "redis"]
        )
        return report.to_dict()


# 全局单例
health_service = HealthService()
