"""
监控仪表盘 (Monitoring Dashboard)
实时性能指标、历史趋势和告警机制
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """指标类型"""
    COUNTER = "counter"           # 计数器
    GAUGE = "gauge"               # 仪表值
    HISTOGRAM = "histogram"        # 直方图
    TIMER = "timer"                # 计时器


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """告警"""
    level: AlertLevel
    message: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric_name: str
    condition: str                    # "gt", "lt", "eq", "gte", "lte"
    threshold: float
    level: AlertLevel
    duration_seconds: int = 60        # 持续时间
    enabled: bool = True


class MetricsCollector:
    """
    指标收集器
    
    收集和聚合各类指标
    """
    
    def __init__(self, retention_minutes: int = 60):
        self.retention_minutes = retention_minutes
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        
        logger.info(f"📊 [指标收集器] 初始化: retention={retention_minutes}分钟")
    
    async def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.COUNTER,
        labels: Optional[Dict[str, str]] = None
    ):
        """记录指标"""
        async with self._lock:
            if name not in self._metrics:
                self._metrics[name] = {
                    "type": metric_type,
                    "values": deque(maxlen=1000),
                    "total": 0.0,
                    "count": 0,
                    "min": float('inf'),
                    "max": float('-inf'),
                    "labels": set()
                }
            
            metric = self._metrics[name]
            timestamp = datetime.now()
            
            point = MetricPoint(
                timestamp=timestamp,
                value=value,
                labels=labels or {}
            )
            
            metric["values"].append(point)
            
            if labels:
                metric["labels"].update(labels.keys())
            
            if metric_type == MetricType.COUNTER:
                metric["total"] += value
                metric["count"] += 1
            elif metric_type == MetricType.GAUGE:
                metric["total"] = value
                metric["count"] += 1
            elif metric_type in [MetricType.HISTOGRAM, MetricType.TIMER]:
                metric["total"] += value
                metric["count"] += 1
                metric["min"] = min(metric["min"], value)
                metric["max"] = max(metric["max"], value)
    
    async def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """递增计数器"""
        await self.record(name, value, MetricType.COUNTER, labels)
    
    async def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """设置仪表值"""
        await self.record(name, value, MetricType.GAUGE, labels)
    
    async def timing(self, name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None):
        """记录时间"""
        await self.record(name, duration_ms, MetricType.TIMER, labels)
    
    async def get_metrics(self, name: str, minutes: int = 5) -> Dict[str, Any]:
        """获取指标数据"""
        async with self._lock:
            if name not in self._metrics:
                return {}
            
            metric = self._metrics[name]
            cutoff = datetime.now() - timedelta(minutes=minutes)
            
            recent_points = [
                p for p in metric["values"]
                if p.timestamp >= cutoff
            ]
            
            if not recent_points:
                return {
                    "name": name,
                    "type": metric["type"],
                    "count": 0
                }
            
            values = [p.value for p in recent_points]
            
            return {
                "name": name,
                "type": metric["type"],
                "count": len(values),
                "total": sum(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "recent": [
                    {
                        "timestamp": p.timestamp.isoformat(),
                        "value": p.value
                    }
                    for p in recent_points[-10:]
                ]
            }
    
    async def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        async with self._lock:
            result = {}
            for name in self._metrics:
                result[name] = await self.get_metrics(name, minutes=1)
            return result


class AlertManager:
    """
    告警管理器
    
    管理告警规则和触发逻辑
    """
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: List[Alert] = []
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._lock = asyncio.Lock()
        self._check_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("🚨 [告警管理器] 初始化完成")
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self._rules[rule.name] = rule
        logger.info(f"🚨 [告警] 添加规则: {rule.name}")
    
    def remove_rule(self, name: str):
        """移除告警规则"""
        if name in self._rules:
            del self._rules[name]
            logger.info(f"🚨 [告警] 移除规则: {name}")
    
    def on_alert(self, callback: Callable[[Alert], None]):
        """注册告警回调"""
        self._alert_callbacks.append(callback)
    
    async def check_condition(self, metric_name: str, value: float) -> Optional[Alert]:
        """检查条件"""
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            if rule.metric_name != metric_name:
                continue
            
            triggered = False
            
            if rule.condition == "gt" and value > rule.threshold:
                triggered = True
            elif rule.condition == "lt" and value < rule.threshold:
                triggered = True
            elif rule.condition == "gte" and value >= rule.threshold:
                triggered = True
            elif rule.condition == "lte" and value <= rule.threshold:
                triggered = True
            elif rule.condition == "eq" and abs(value - rule.threshold) < 0.001:
                triggered = True
            
            if triggered:
                alert = Alert(
                    level=rule.level,
                    message=f"{metric_name}: {value:.2f} {rule.condition} {rule.threshold}",
                    metric_name=metric_name,
                    current_value=value,
                    threshold=rule.threshold
                )
                
                await self._trigger_alert(alert)
                return alert
        
        return None
    
    async def _trigger_alert(self, alert: Alert):
        """触发告警"""
        async with self._lock:
            self._alerts.append(alert)
            
            # 保持最近100条告警
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-100:]
        
        logger.warning(f"🚨 [告警] 触发: {alert.level.value} - {alert.message}")
        
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"❌ [告警] 回调执行失败: {e}")
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        async with self._lock:
            return [
                {
                    "level": a.level.value,
                    "message": a.message,
                    "metric_name": a.metric_name,
                    "current_value": a.current_value,
                    "threshold": a.threshold,
                    "timestamp": a.timestamp.isoformat(),
                    "resolved": a.resolved
                }
                for a in self._alerts
                if not a.resolved
            ]
    
    async def resolve_alert(self, metric_name: str):
        """解决告警"""
        async with self._lock:
            for alert in self._alerts:
                if alert.metric_name == metric_name and not alert.resolved:
                    alert.resolved = True
                    logger.info(f"✅ [告警] 已解决: {metric_name}")


class PerformanceTracker:
    """
    性能追踪器
    
    追踪请求处理时间和吞吐量
    """
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self._active_requests: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def start_request(self, request_id: str):
        """开始请求追踪"""
        async with self._lock:
            self._active_requests[request_id] = time.time()
            await self.collector.increment("requests.active")
    
    async def end_request(self, request_id: str, success: bool = True):
        """结束请求追踪"""
        async with self._lock:
            if request_id not in self._active_requests:
                return
            
            start_time = self._active_requests.pop(request_id)
            duration_ms = (time.time() - start_time) * 1000
            
            await self.collector.timing("request.duration", duration_ms)
            await self.collector.increment("requests.completed")
            
            if success:
                await self.collector.increment("requests.success")
            else:
                await self.collector.increment("requests.failed")
    
    async def get_active_count(self) -> int:
        """获取活跃请求数"""
        async with self._lock:
            return len(self._active_requests)


class MonitoringDashboard:
    """
    监控仪表盘
    
    整合指标收集、告警和追踪的监控中心
    """
    
    def __init__(self):
        self.collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self._trackers: Dict[str, PerformanceTracker] = {}
        self._start_time = datetime.now()
        self._lock = asyncio.Lock()
        
        self._setup_default_rules()
        
        logger.info("📈 [监控仪表盘] 初始化完成")
    
    def _setup_default_rules(self):
        """设置默认告警规则"""
        self.alert_manager.add_rule(AlertRule(
            name="high_error_rate",
            metric_name="requests.error_rate",
            condition="gt",
            threshold=0.1,
            level=AlertLevel.ERROR
        ))
        
        self.alert_manager.add_rule(AlertRule(
            name="high_latency",
            metric_name="request.duration.avg",
            condition="gt",
            threshold=5000,
            level=AlertLevel.WARNING
        ))
        
        self.alert_manager.add_rule(AlertRule(
            name="cache_low_hit_rate",
            metric_name="cache.hit_rate",
            condition="lt",
            threshold=0.5,
            level=AlertLevel.WARNING
        ))
    
    def get_tracker(self, name: str) -> PerformanceTracker:
        """获取性能追踪器"""
        if name not in self._trackers:
            self._trackers[name] = PerformanceTracker(self.collector)
        return self._trackers[name]
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        uptime = (datetime.now() - self._start_time).total_seconds()
        
        metrics = await self.collector.get_all_metrics()
        
        request_metrics = metrics.get("request.duration", {})
        cache_metrics = metrics.get("cache.hit_rate", {})
        
        return {
            "uptime_seconds": uptime,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "requests": {
                    "total": metrics.get("requests.completed", {}).get("count", 0),
                    "active": len(self._trackers),
                    "success_rate": self._calculate_success_rate(metrics),
                    "avg_duration_ms": request_metrics.get("avg", 0)
                },
                "cache": {
                    "hit_rate": cache_metrics.get("avg", 0),
                    "hits": metrics.get("cache.hits", {}).get("count", 0),
                    "misses": metrics.get("cache.misses", {}).get("count", 0)
                },
                "agents": self._get_agent_metrics(metrics)
            },
            "alerts": await self.alert_manager.get_active_alerts(),
            "health": self._calculate_health(metrics)
        }
    
    def _calculate_success_rate(self, metrics: Dict[str, Any]) -> float:
        """计算成功率"""
        total = metrics.get("requests.completed", {}).get("count", 0)
        failed = metrics.get("requests.failed", {}).get("count", 0)
        
        if total == 0:
            return 1.0
        
        return (total - failed) / total
    
    def _get_agent_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """获取智能体指标"""
        agent_metrics = {}
        
        for key, value in metrics.items():
            if key.startswith("agent."):
                parts = key.split(".")
                if len(parts) >= 2:
                    agent_name = parts[1]
                    metric_type = parts[2] if len(parts) > 2 else "count"
                    
                    if agent_name not in agent_metrics:
                        agent_metrics[agent_name] = {}
                    
                    agent_metrics[agent_name][metric_type] = value.get("avg", value.get("count", 0))
        
        return agent_metrics
    
    def _calculate_health(self, metrics: Dict[str, Any]) -> str:
        """计算健康状态"""
        error_rate = metrics.get("requests.error_rate", {}).get("avg", 0)
        avg_duration = metrics.get("request.duration.avg", {}).get("avg", 0)
        cache_hit_rate = metrics.get("cache.hit_rate", {}).get("avg", 1.0)
        
        if error_rate > 0.1 or avg_duration > 10000:
            return "critical"
        elif error_rate > 0.05 or avg_duration > 5000:
            return "degraded"
        elif cache_hit_rate < 0.3:
            return "warning"
        
        return "healthy"
    
    async def export_prometheus_format(self) -> str:
        """导出Prometheus格式"""
        lines = []
        
        metrics = await self.collector.get_all_metrics()
        
        for name, data in metrics.items():
            if "total" in data:
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {data['total']}")
            
            if data.get("type") == MetricType.HISTOGRAM.value:
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_sum {data.get('total', 0)}")
                lines.append(f"{name}_count {data.get('count', 0)}")
        
        return "\n".join(lines)


# 全局仪表盘实例
_dashboard: Optional[MonitoringDashboard] = None


def get_dashboard() -> MonitoringDashboard:
    """获取全局仪表盘实例"""
    global _dashboard
    if _dashboard is None:
        _dashboard = MonitoringDashboard()
    return _dashboard


class RequestContext:
    """
    请求上下文
    
    用于追踪单个请求的生命周期
    """
    
    def __init__(self, request_id: str, dashboard: MonitoringDashboard):
        self.request_id = request_id
        self.dashboard = dashboard
        self.tracker = dashboard.get_tracker("default")
        self.start_time = time.time()
        self.metadata: Dict[str, Any] = {}
    
    async def __aenter__(self):
        await self.tracker.start_request(self.request_id)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        await self.tracker.end_request(self.request_id, success)
        
        if exc_type:
            await self.dashboard.collector.increment(
                "errors",
                labels={"type": exc_type.__name__}
            )
    
    def set_metadata(self, key: str, value: Any):
        """设置元数据"""
        self.metadata[key] = value
    
    def get_duration_ms(self) -> float:
        """获取已执行时间"""
        return (time.time() - self.start_time) * 1000
