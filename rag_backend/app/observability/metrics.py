"""
指标收集系统

基于 OpenTelemetry 的指标收集实现

功能：
1. Counter（计数器）
2. Histogram（直方图）
3. Gauge（仪表）
4. 指标聚合和导出
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class MetricsConfig:
    """指标配置"""
    service_name: str = "rag-backend"
    enabled: bool = True
    export_interval: int = 60  # 秒
    max_metrics_per_type: int = 1000


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Counter:
    """
    计数器指标
    
    用于记录单调递增的值，如请求数、错误数等
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        unit: str = "1",
        initial_value: float = 0
    ):
        """
        初始化计数器
        
        Args:
            name: 指标名称
            description: 描述
            unit: 单位
            initial_value: 初始值
        """
        self.name = name
        self.description = description
        self.unit = unit
        self._value = initial_value
        self._values_by_label: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def add(self, amount: float = 1, labels: Optional[Dict[str, str]] = None):
        """
        增加计数
        
        Args:
            amount: 增加量
            labels: 标签
        """
        with self._lock:
            if labels:
                label_key = self._make_label_key(labels)
                self._values_by_label[label_key] += amount
            else:
                self._value += amount
    
    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """获取当前值"""
        with self._lock:
            if labels:
                label_key = self._make_label_key(labels)
                return self._values_by_label.get(label_key, 0.0)
            return self._value
    
    def _make_label_key(self, labels: Dict[str, str]) -> str:
        """生成标签键"""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def collect(self) -> List[MetricPoint]:
        """收集指标数据"""
        with self._lock:
            points = []
            
            # 全局值
            if self._value > 0:
                points.append(MetricPoint(
                    timestamp=datetime.now(),
                    value=self._value
                ))
            
            # 按标签的值
            for label_key, value in self._values_by_label.items():
                labels = dict(kv.split("=") for kv in label_key.split(","))
                points.append(MetricPoint(
                    timestamp=datetime.now(),
                    value=value,
                    labels=labels
                ))
            
            return points


class Histogram:
    """
    直方图指标
    
    用于记录值的分布，如延迟、响应大小等
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        unit: str = "ms",
        boundaries: Optional[List[float]] = None
    ):
        """
        初始化直方图
        
        Args:
            name: 指标名称
            description: 描述
            unit: 单位
            boundaries: 边界值
        """
        self.name = name
        self.description = description
        self.unit = unit
        self.boundaries = boundaries or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        
        self._count = 0
        self._sum = 0.0
        self._min = float('inf')
        self._max = float('-inf')
        self._buckets: Dict[float, int] = defaultdict(int)
        self._values_by_label: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0, "sum": 0, "min": float('inf'), "max": float('-inf')
        })
        self._lock = threading.Lock()
    
    def record(self, value: float, labels: Optional[Dict[str, str]] = None):
        """
        记录值
        
        Args:
            value: 值
            labels: 标签
        """
        with self._lock:
            if labels:
                label_key = self._make_label_key(labels)
                data = self._values_by_label[label_key]
            else:
                data = {"count": self._count, "sum": self._sum, "min": self._min, "max": self._max}
            
            data["count"] += 1
            data["sum"] += value
            data["min"] = min(data["min"], value)
            data["max"] = max(data["max"], value)
            
            # 更新 bucket
            for boundary in self.boundaries:
                if value <= boundary:
                    if labels:
                        self._values_by_label[label_key][f"le_{boundary}"] += 1
                    else:
                        self._buckets[boundary] += 1
            
            if labels:
                self._values_by_label[label_key] = data
            else:
                self._count = data["count"]
                self._sum = data["sum"]
                self._min = data["min"]
                self._max = data["max"]
    
    def _make_label_key(self, labels: Dict[str, str]) -> str:
        """生成标签键"""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def get_stats(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """获取统计信息"""
        with self._lock:
            if labels:
                label_key = self._make_label_key(labels)
                data = self._values_by_label.get(label_key, {})
            else:
                data = {
                    "count": self._count,
                    "sum": self._sum,
                    "min": self._min,
                    "max": self._max
                }
            
            count = data.get("count", 0)
            if count == 0:
                return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
            
            return {
                "count": count,
                "sum": data.get("sum", 0),
                "avg": data.get("sum", 0) / count,
                "min": data.get("min", 0),
                "max": data.get("max", 0)
            }
    
    def collect(self) -> List[MetricPoint]:
        """收集指标数据"""
        with self._lock:
            points = []
            
            stats = self.get_stats()
            points.append(MetricPoint(
                timestamp=datetime.now(),
                value=stats["count"],
                labels={"stat": "count"}
            ))
            points.append(MetricPoint(
                timestamp=datetime.now(),
                value=stats["sum"],
                labels={"stat": "sum"}
            ))
            points.append(MetricPoint(
                timestamp=datetime.now(),
                value=stats["avg"],
                labels={"stat": "avg"}
            ))
            
            return points


class Gauge:
    """
    仪表指标
    
    用于记录当前值，可以增加或减少，如CPU使用率、队列长度等
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        unit: str = "1",
        initial_value: float = 0
    ):
        """
        初始化仪表
        
        Args:
            name: 指标名称
            description: 描述
            unit: 单位
            initial_value: 初始值
        """
        self.name = name
        self.description = description
        self.unit = unit
        self._value = initial_value
        self._values_by_label: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        """设置值"""
        with self._lock:
            if labels:
                label_key = self._make_label_key(labels)
                self._values_by_label[label_key] = value
            else:
                self._value = value
    
    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """获取当前值"""
        with self._lock:
            if labels:
                label_key = self._make_label_key(labels)
                return self._values_by_label.get(label_key, 0.0)
            return self._value
    
    def _make_label_key(self, labels: Dict[str, str]) -> str:
        """生成标签键"""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def collect(self) -> List[MetricPoint]:
        """收集指标数据"""
        with self._lock:
            points = []
            
            if self._value != 0:
                points.append(MetricPoint(
                    timestamp=datetime.now(),
                    value=self._value
                ))
            
            for label_key, value in self._values_by_label.items():
                labels = dict(kv.split("=") for kv in label_key.split(","))
                points.append(MetricPoint(
                    timestamp=datetime.now(),
                    value=value,
                    labels=labels
                ))
            
            return points


class MetricsCollector:
    """
    指标收集器
    
    管理所有指标，提供统一的收集和导出接口
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        """
        初始化指标收集器
        
        Args:
            config: 配置
        """
        self.config = config or MetricsConfig()
        self._enabled = self.config.enabled
        
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}
        
        self._lock = threading.Lock()
        
        # 注册默认指标
        self._register_default_metrics()
        
        logger.info(f"[Metrics] 初始化: service={self.config.service_name}")
    
    def _register_default_metrics(self):
        """注册默认指标"""
        # 请求相关
        self.create_counter(
            "rag.requests.total",
            "Total number of requests"
        )
        
        self.create_counter(
            "rag.requests.errors",
            "Total number of request errors"
        )
        
        self.create_histogram(
            "rag.request.duration",
            "Request duration in milliseconds",
            unit="ms"
        )
        
        # Agent 相关
        self.create_counter(
            "rag.agents.invocations",
            "Number of agent invocations"
        )
        
        self.create_histogram(
            "rag.agent.execution.duration",
            "Agent execution duration",
            unit="ms"
        )
        
        # 任务相关
        self.create_gauge(
            "rag.tasks.pending",
            "Number of pending tasks"
        )
        
        self.create_gauge(
            "rag.tasks.running",
            "Number of running tasks"
        )
    
    def create_counter(
        self,
        name: str,
        description: str = "",
        unit: str = "1"
    ) -> Counter:
        """
        创建计数器
        
        Args:
            name: 指标名称
            description: 描述
            unit: 单位
            
        Returns:
            Counter 实例
        """
        with self._lock:
            if name in self._counters:
                return self._counters[name]
            
            counter = Counter(name, description, unit)
            self._counters[name] = counter
            
            logger.debug(f"[Metrics] 创建计数器: {name}")
            return counter
    
    def create_histogram(
        self,
        name: str,
        description: str = "",
        unit: str = "1",
        boundaries: Optional[List[float]] = None
    ) -> Histogram:
        """
        创建直方图
        
        Args:
            name: 指标名称
            description: 描述
            unit: 单位
            boundaries: 边界值
            
        Returns:
            Histogram 实例
        """
        with self._lock:
            if name in self._histograms:
                return self._histograms[name]
            
            histogram = Histogram(name, description, unit, boundaries)
            self._histograms[name] = histogram
            
            logger.debug(f"[Metrics] 创建直方图: {name}")
            return histogram
    
    def create_gauge(
        self,
        name: str,
        description: str = "",
        unit: str = "1"
    ) -> Gauge:
        """
        创建仪表
        
        Args:
            name: 指标名称
            description: 描述
            unit: 单位
            
        Returns:
            Gauge 实例
        """
        with self._lock:
            if name in self._gauges:
                return self._gauges[name]
            
            gauge = Gauge(name, description, unit)
            self._gauges[name] = gauge
            
            logger.debug(f"[Metrics] 创建仪表: {name}")
            return gauge
    
    def get_counter(self, name: str) -> Optional[Counter]:
        """获取计数器"""
        return self._counters.get(name)
    
    def get_histogram(self, name: str) -> Optional[Histogram]:
        """获取直方图"""
        return self._histograms.get(name)
    
    def get_gauge(self, name: str) -> Optional[Gauge]:
        """获取仪表"""
        return self._gauges.get(name)
    
    def record_request(self, duration_ms: float, labels: Optional[Dict[str, str]] = None):
        """
        记录请求
        
        Args:
            duration_ms: 持续时间（毫秒）
            labels: 标签
        """
        if not self._enabled:
            return
        
        self.get_counter("rag.requests.total").add(1, labels)
        self.get_histogram("rag.request.duration").record(duration_ms, labels)
    
    def record_agent_invocation(
        self,
        agent_name: str,
        duration_ms: float,
        success: bool = True
    ):
        """
        记录 Agent 调用
        
        Args:
            agent_name: Agent 名称
            duration_ms: 持续时间
            success: 是否成功
        """
        if not self._enabled:
            return
        
        labels = {"agent": agent_name, "status": "success" if success else "error"}
        
        self.get_counter("rag.agents.invocations").add(1, labels)
        self.get_histogram("rag.agent.execution.duration").record(
            duration_ms,
            {"agent": agent_name}
        )
        
        if not success:
            self.get_counter("rag.requests.errors").add(1, labels)
    
    def set_pending_tasks(self, count: int):
        """设置待处理任务数"""
        if self._enabled:
            self.get_gauge("rag.tasks.pending").set(count)
    
    def set_running_tasks(self, count: int):
        """设置运行中任务数"""
        if self._enabled:
            self.get_gauge("rag.tasks.running").set(count)
    
    def collect_all(self) -> Dict[str, List[MetricPoint]]:
        """
        收集所有指标
        
        Returns:
            指标点字典
        """
        result = {}
        
        with self._lock:
            for name, counter in self._counters.items():
                result[name] = counter.collect()
            
            for name, histogram in self._histograms.items():
                result[name] = histogram.collect()
            
            for name, gauge in self._gauges.items():
                result[name] = gauge.collect()
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "enabled": self._enabled,
                "counters": len(self._counters),
                "histograms": len(self._histograms),
                "gauges": len(self._gauges),
                "total_metrics": len(self._counters) + len(self._histograms) + len(self._gauges)
            }
    
    def export_prometheus(self) -> str:
        """
        导出 Prometheus 格式
        
        Returns:
            Prometheus 格式的文本
        """
        lines = []
        
        all_metrics = self.collect_all()
        
        for metric_name, points in all_metrics.items():
            for point in points:
                labels_str = ""
                if point.labels:
                    labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in point.labels.items()) + "}"
                
                lines.append(f"{metric_name}{labels_str} {point.value}")
        
        return "\n".join(lines)


# 全局指标收集器
_metrics_collector: Optional[MetricsCollector] = None


def init_metrics(config: Optional[MetricsConfig] = None) -> MetricsCollector:
    """初始化全局指标收集器"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(config)
    return _metrics_collector


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_request(duration_ms: float, labels: Optional[Dict[str, str]] = None):
    """便捷函数：记录请求"""
    get_metrics_collector().record_request(duration_ms, labels)


def record_agent_invocation(
    agent_name: str,
    duration_ms: float,
    success: bool = True
):
    """便捷函数：记录 Agent 调用"""
    get_metrics_collector().record_agent_invocation(agent_name, duration_ms, success)
