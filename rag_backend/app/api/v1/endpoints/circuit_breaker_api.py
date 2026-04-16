"""
熔断器管理 API

提供熔断器状态监控和管理接口
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.langgraph.circuit_breaker_integration import (
    get_circuit_breaker_manager,
    initialize_circuit_breaker_manager
)
from app.multi_agent_system.async_task_scheduler import (
    CircuitBreakerConfig,
    CircuitState
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/circuit-breaker", tags=["熔断器管理"])


class CircuitBreakerConfigRequest(BaseModel):
    """熔断器配置请求"""
    failure_threshold: int = Field(5, ge=1, le=100, description="失败次数阈值")
    success_threshold: int = Field(2, ge=1, le=20, description="恢复需要的成功次数")
    timeout: float = Field(60.0, ge=1.0, le=3600.0, description="熔断持续时间（秒）")
    half_open_max_calls: int = Field(3, ge=1, le=20, description="半开状态最大并发调用数")


class CircuitBreakerStatus(BaseModel):
    """熔断器状态"""
    name: str
    state: str
    failure_count: int
    success_count: int
    last_failure_time: Optional[str] = None


class RegisterBreakerRequest(BaseModel):
    """注册熔断器请求"""
    name: str = Field(..., min_length=1, max_length=100, description="熔断器名称")
    config: Optional[CircuitBreakerConfigRequest] = Field(None, description="熔断器配置")


@router.post("/register", response_model=CircuitBreakerStatus)
async def register_circuit_breaker(request: RegisterBreakerRequest):
    """
    注册新的熔断器
    
    Args:
        request: 注册请求
        
    Returns:
        CircuitBreakerStatus: 熔断器状态
    """
    try:
        manager = get_circuit_breaker_manager()
        await manager.initialize()
        
        config = None
        if request.config:
            config = CircuitBreakerConfig(
                failure_threshold=request.config.failure_threshold,
                success_threshold=request.config.success_threshold,
                timeout=request.config.timeout,
                half_open_max_calls=request.config.half_open_max_calls
            )
        
        breaker = manager.register_breaker(request.name, config)
        stats = breaker.get_stats()
        
        logger.info(f"✅ 注册熔断器: {request.name}")
        
        return CircuitBreakerStatus(
            name=stats["name"],
            state=stats["state"],
            failure_count=stats["failure_count"],
            success_count=stats["success_count"],
            last_failure_time=stats["last_failure_time"]
        )
        
    except Exception as e:
        logger.error(f"❌ 注册熔断器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{breaker_name}", response_model=CircuitBreakerStatus)
async def get_breaker_status(breaker_name: str):
    """
    获取熔断器状态
    
    Args:
        breaker_name: 熔断器名称
        
    Returns:
        CircuitBreakerStatus: 熔断器状态
    """
    try:
        manager = get_circuit_breaker_manager()
        stats = manager.get_breaker_stats(breaker_name)
        
        if not stats:
            raise HTTPException(status_code=404, detail=f"熔断器 {breaker_name} 未找到")
        
        return CircuitBreakerStatus(
            name=stats["name"],
            state=stats["state"],
            failure_count=stats["failure_count"],
            success_count=stats["success_count"],
            last_failure_time=stats["last_failure_time"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取熔断器状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_all_breakers_status():
    """
    获取所有熔断器状态
    
    Returns:
        Dict: 所有熔断器的状态信息
    """
    try:
        manager = get_circuit_breaker_manager()
        all_stats = manager.get_all_stats()
        
        return {
            "total_breakers": len(all_stats),
            "breakers": {
                name: CircuitBreakerStatus(
                    name=stats["name"],
                    state=stats["state"],
                    failure_count=stats["failure_count"],
                    success_count=stats["success_count"],
                    last_failure_time=stats["last_failure_time"]
                )
                for name, stats in all_stats.items()
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 获取所有熔断器状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset/{breaker_name}")
async def reset_breaker(breaker_name: str):
    """
    手动重置熔断器
    
    将熔断器状态重置为 CLOSED（关闭）状态
    
    Args:
        breaker_name: 熔断器名称
        
    Returns:
        Dict: 重置结果
    """
    try:
        manager = get_circuit_breaker_manager()
        stats = manager.get_breaker_stats(breaker_name)
        
        if not stats:
            raise HTTPException(status_code=404, detail=f"熔断器 {breaker_name} 未找到")
        
        breaker = manager._breakers.get(breaker_name)
        if breaker:
            breaker.state = CircuitState.CLOSED
            breaker.failure_count = 0
            breaker.success_count = 0
            breaker.last_failure_time = None
            breaker.half_open_calls = 0
            
            logger.info(f"🔄 手动重置熔断器: {breaker_name}")
            
            return {
                "status": "success",
                "message": f"熔断器 {breaker_name} 已重置",
                "new_state": CircuitState.CLOSED.value
            }
        else:
            raise HTTPException(status_code=500, detail="熔断器实例获取失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 重置熔断器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unregister/{breaker_name}")
async def unregister_breaker(breaker_name: str):
    """
    注销熔断器
    
    Args:
        breaker_name: 熔断器名称
        
    Returns:
        Dict: 注销结果
    """
    try:
        manager = get_circuit_breaker_manager()
        
        if breaker_name not in manager._breakers:
            raise HTTPException(status_code=404, detail=f"熔断器 {breaker_name} 未找到")
        
        del manager._breakers[breaker_name]
        
        logger.info(f"🗑️ 注销熔断器: {breaker_name}")
        
        return {
            "status": "success",
            "message": f"熔断器 {breaker_name} 已注销"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 注销熔断器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def circuit_breaker_health():
    """
    熔断器系统健康检查
    
    Returns:
        Dict: 健康状态信息
    """
    try:
        manager = get_circuit_breaker_manager()
        all_stats = manager.get_all_stats()
        
        open_breakers = [
            name for name, stats in all_stats.items()
            if stats["state"] == CircuitState.OPEN.value
        ]
        
        half_open_breakers = [
            name for name, stats in all_stats.items()
            if stats["state"] == CircuitState.HALF_OPEN.value
        ]
        
        total_failures = sum(
            stats["failure_count"]
            for stats in all_stats.values()
        )
        
        return {
            "status": "healthy" if not open_breakers else "degraded",
            "total_breakers": len(all_stats),
            "open_breakers": open_breakers,
            "half_open_breakers": half_open_breakers,
            "total_failures": total_failures,
            "needs_attention": len(open_breakers) > 0
        }
        
    except Exception as e:
        logger.error(f"❌ 健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.post("/initialize")
async def initialize_breakers():
    """
    初始化默认熔断器
    
    注册常用的熔断器：LLM服务、外部API、MCP工具
    
    Returns:
        Dict: 初始化结果
    """
    try:
        await initialize_circuit_breaker_manager()
        
        manager = get_circuit_breaker_manager()
        all_stats = manager.get_all_stats()
        
        logger.info("✅ 熔断器管理器初始化完成")
        
        return {
            "status": "success",
            "message": "熔断器管理器初始化完成",
            "registered_breakers": list(all_stats.keys())
        }
        
    except Exception as e:
        logger.error(f"❌ 初始化熔断器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
