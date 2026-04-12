"""
政策更新调度器
自动化定时采集和更新政策
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UpdateFrequency(str, Enum):
    """更新频率枚举"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class SchedulerConfig:
    """调度器配置"""
    frequency: UpdateFrequency = UpdateFrequency.DAILY
    keywords: List[str] = None
    enabled_sources: List[str] = None
    time_of_day: str = "03:00"
    day_of_week: int = 1
    day_of_month: int = 1


class PolicyScheduler:
    """
    政策更新调度器
    
    功能：
    1. 定时触发政策采集任务
    2. 支持多种更新频率
    3. 记录采集历史
    4. 发送采集报告
    """
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: Optional[datetime] = None
        self._last_status: Optional[Dict[str, Any]] = None
        self._run_history: List[Dict[str, Any]] = []
        
        self._config = SchedulerConfig()
    
    @property
    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running
    
    def configure(self, config: SchedulerConfig):
        """
        配置调度器
        
        Args:
            config: 调度配置
        """
        self._config = config
        logger.info(f"⏰ 调度器配置已更新: {config.frequency.value}")
        if config.keywords:
            logger.info(f"   关键词: {', '.join(config.keywords[:5])}...")
    
    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("⚠️ 调度器已在运行中")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("🚀 政策调度器已启动")
    
    async def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 政策调度器已停止")
    
    async def _run_scheduler(self):
        """运行调度循环"""
        while self._running:
            try:
                now = datetime.now()
                
                if self._should_run(now):
                    await self._run_collection()
                    self._last_run = now
                
                sleep_time = self._calculate_sleep_time(now)
                logger.debug(f"💤 调度器休眠 {sleep_time} 秒")
                
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 调度器数据异常: {e}", exc_info=True)
                await asyncio.sleep(60)
            except (OSError, IOError) as e:
                logger.error(f"❌ 调度器IO异常: {e}", exc_info=True)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"❌ 调度器异常: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    def _should_run(self, now: datetime) -> bool:
        """
        判断是否应该运行采集任务
        
        Args:
            now: 当前时间
            
        Returns:
            bool: 是否应该运行
        """
        if self._last_run is None:
            return True
        
        time_diff = now - self._last_run
        
        if self._config.frequency == UpdateFrequency.HOURLY:
            return time_diff >= timedelta(hours=1)
        
        elif self._config.frequency == UpdateFrequency.DAILY:
            return time_diff >= timedelta(days=1)
        
        elif self._config.frequency == UpdateFrequency.WEEKLY:
            return time_diff >= timedelta(weeks=1)
        
        elif self._config.frequency == UpdateFrequency.MONTHLY:
            return time_diff >= timedelta(days=30)
        
        return False
    
    def _calculate_sleep_time(self, now: datetime) -> float:
        """
        计算休眠时间
        
        Args:
            now: 当前时间
            
        Returns:
            float: 休眠时间（秒）
        """
        if self._config.frequency == UpdateFrequency.HOURLY:
            next_run = now + timedelta(hours=1)
            next_run = next_run.replace(minute=0, second=0, microsecond=0)
        elif self._config.frequency == UpdateFrequency.DAILY:
            next_run = now + timedelta(days=1)
            try:
                hour, minute = map(int, self._config.time_of_day.split(":"))
                next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except (ValueError, AttributeError):
                next_run = next_run.replace(hour=3, minute=0, second=0, microsecond=0)
        else:
            next_run = now + timedelta(hours=1)
        
        sleep_seconds = (next_run - now).total_seconds()
        return max(60, min(sleep_seconds, 3600))
    
    async def _run_collection(self):
        """执行采集任务"""
        logger.info("📦 开始执行政策采集任务...")
        
        start_time = datetime.now()
        status = {
            "start_time": start_time,
            "sources": [],
            "total_collected": 0,
            "total_saved": 0,
            "errors": [],
            "status": "running"
        }
        
        try:
            from .policy_collector import policy_collector
            from ..multi_agent_system.agents.policy_agent import PolicyAgent
            
            for source in policy_collector.sources:
                if self._config.enabled_sources and source.name not in self._config.enabled_sources:
                    continue
                
                if not source.enabled:
                    continue
                
                logger.info(f"📥 采集来源: {source.name}")
                
                try:
                    policies = await policy_collector.collect_from_source(
                        source,
                        self._config.keywords
                    )
                    
                    status["sources"].append({
                        "name": source.name,
                        "collected": len(policies),
                        "success": True
                    })
                    
                    status["total_collected"] += len(policies)
                    
                except (ValueError, KeyError) as e:
                    logger.error(f"❌ 采集数据失败 [{source.name}]: {e}")
                    status["sources"].append({
                        "name": source.name,
                        "collected": 0,
                        "success": False,
                        "error": f"数据错误: {str(e)}"
                    })
                    status["errors"].append(f"{source.name}: 数据错误")
                except (OSError, IOError) as e:
                    logger.error(f"❌ 采集IO失败 [{source.name}]: {e}")
                    status["sources"].append({
                        "name": source.name,
                        "collected": 0,
                        "success": False,
                        "error": f"IO错误: {str(e)}"
                    })
                    status["errors"].append(f"{source.name}: IO错误")
                except Exception as e:
                    logger.error(f"❌ 采集失败 [{source.name}]: {e}")
                    status["sources"].append({
                        "name": source.name,
                        "collected": 0,
                        "success": False,
                        "error": str(e)
                    })
                    status["errors"].append(f"{source.name}: {str(e)}")
            
            status["status"] = "success"
            logger.info(f"✅ 采集任务完成: {status['total_collected']} 条政策")
            
        except (ValueError, KeyError) as e:
            status["status"] = "failed"
            status["errors"].append(f"数据错误: {str(e)}")
        except (OSError, IOError) as e:
            status["status"] = "failed"
            status["errors"].append(f"IO错误: {str(e)}")
            return status
        except Exception as e:
            status["status"] = "failed"
            status["errors"].append(str(e))
            logger.error(f"❌ 采集任务失败: {e}", exc_info=True)
            return status
        
        finally:
            status["end_time"] = datetime.now()
            status["duration"] = (status["end_time"] - status["start_time"]).total_seconds()
            
            self._last_status = status
            self._run_history.append(status)
            
            if len(self._run_history) > 100:
                self._run_history = self._run_history[-100:]
    
    async def trigger_manual_update(self, keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        手动触发更新
        
        Args:
            keywords: 关键词列表
            
        Returns:
            Dict: 更新结果
        """
        logger.info("🔧 手动触发政策更新...")
        
        original_keywords = self._config.keywords
        if keywords:
            self._config.keywords = keywords
        
        await self._run_collection()
        
        if keywords:
            self._config.keywords = original_keywords
        
        return self._last_status or {}
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取调度器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_status": self._last_status,
            "config": {
                "frequency": self._config.frequency.value,
                "keywords_count": len(self._config.keywords) if self._config.keywords else 0,
                "enabled_sources": self._config.enabled_sources
            },
            "history_count": len(self._run_history)
        }
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取运行历史
        
        Args:
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 历史记录
        """
        return self._run_history[-limit:]


policy_scheduler = PolicyScheduler()
