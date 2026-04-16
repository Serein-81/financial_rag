"""
财务健康智能监控 Pydantic Schema 定义
用于财务异常检测和预警系统
"""

from typing import List, Dict, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum


class AnomalyType(str, Enum):
    """财务异常类型"""
    REVENUE_DROP = "revenue_drop"  # 收入断崖式下跌
    COST_SURGE = "cost_surge"  # 成本异常飙升
    NEGATIVE_CASHFLOW = "negative_cashflow"  # 现金流持续为负
    EXTENDED_RECEIVABLES = "extended_receivables"  # 回款周期延长
    MARGIN_DECLINE = "margin_decline"  # 毛利率持续下降
    LEVERAGE_EXCEED = "leverage_exceed"  # 资产负债率超标
    LIQUIDITY_WARNING = "liquidity_warning"  # 流动性不足
    WORKING_CAPITAL_ISSUE = "working_capital_issue"  # 营运资本问题


class SeverityLevel(str, Enum):
    """严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, Enum):
    """异常状态"""
    DETECTED = "detected"  # 已检测
    INVESTIGATING = "investigating"  # 调查中
    ACKNOWLEDGED = "acknowledged"  # 已确认
    RESOLVED = "resolved"  # 已解决
    DISMISSED = "dismissed"  # 已驳回


class MonitoringFrequency(str, Enum):
    """监控频率"""
    REAL_TIME = "real_time"  # 实时
    DAILY = "daily"  # 每日
    WEEKLY = "weekly"  # 每周
    MONTHLY = "monthly"  # 每月


class AnomalyDetectionRule(BaseModel):
    """异常检测规则"""
    rule_id: str = Field(..., description="规则ID")
    anomaly_type: AnomalyType = Field(..., description="异常类型")
    condition: str = Field(..., description="触发条件")
    threshold: float = Field(..., description="阈值")
    severity: SeverityLevel = Field(..., description="默认严重程度")
    lookback_periods: int = Field(default=3, description="回溯期数")
    enabled: bool = Field(default=True, description="是否启用")


class FinancialMetric(BaseModel):
    """财务指标"""
    name: str = Field(..., description="指标名称")
    value: float = Field(..., description="当前值")
    unit: str = Field(default="", description="单位")
    formatted_value: str = Field(..., description="格式化值")
    change_percentage: Optional[float] = Field(None, description="变化百分比")
    trend: str = Field(..., description="趋势：up/down/stable")
    status: str = Field(..., description="状态：normal/warning/high")
    benchmark: Optional[float] = Field(None, description="基准值")
    benchmark_comparison: Optional[str] = Field(None, description="与基准对比")


class AnomalyItem(BaseModel):
    """异常项目"""
    anomaly_id: str = Field(..., description="异常ID")
    anomaly_type: AnomalyType = Field(..., description="异常类型")
    severity: SeverityLevel = Field(..., description="严重程度")
    status: AnomalyStatus = Field(..., description="状态")
    detected_at: datetime = Field(..., description="检测时间")
    title: str = Field(..., description="异常标题")
    description: str = Field(..., description="异常描述")
    affected_metrics: List[str] = Field(default_factory=list, description="影响的指标")
    current_value: Optional[float] = Field(None, description="当前值")
    threshold_value: Optional[float] = Field(None, description="阈值")
    deviation_percentage: Optional[float] = Field(None, description="偏离百分比")
    potential_impact: str = Field(..., description="潜在影响")
    suggested_actions: List[str] = Field(default_factory=list, description="建议措施")
    evidence: List[str] = Field(default_factory=list, description="证据")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="置信度")


class FinancialHealthDashboard(BaseModel):
    """财务健康仪表盘"""
    dashboard_id: str = Field(..., description="仪表盘ID")
    tenant_id: str = Field(..., description="租户ID")
    generated_at: datetime = Field(..., description="生成时间")
    period: str = Field(..., description="统计期间")
    
    overall_health_score: float = Field(..., ge=0.0, le=100.0, description="综合健康评分")
    health_status: str = Field(..., description="健康状态：healthy/warning/critical")
    
    key_metrics: List[FinancialMetric] = Field(default_factory=list, description="关键财务指标")
    
    active_anomalies_count: int = Field(0, description="活跃异常数量")
    critical_anomalies_count: int = Field(0, description="严重异常数量")
    recent_anomalies: List[AnomalyItem] = Field(default_factory=list, description="最近异常")
    
    cash_flow_status: str = Field(..., description="现金流状态")
    profitability_status: str = Field(..., description="盈利能力状态")
    liquidity_status: str = Field(..., description="流动性状态")
    leverage_status: str = Field(..., description="杠杆状态")
    
    summary: str = Field(..., description="摘要")


class FinancialHealthMonitorRequest(BaseModel):
    """财务健康监控请求"""
    tenant_id: Optional[str] = Field(None, description="租户ID（可省略，自动从认证用户获取）")
    user_id: Optional[str] = Field(None, description="用户ID（可省略，自动从认证用户获取）")
    period_start: date = Field(..., description="监控期间开始")
    period_end: date = Field(..., description="监控期间结束")
    include_anomaly_detection: bool = Field(default=True, description="是否包含异常检测")
    include_trend_analysis: bool = Field(default=True, description="是否包含趋势分析")
    include_benchmark: bool = Field(default=False, description="是否包含行业基准对比")

    class Config:
        json_schema_extra = {
            "example": {
                "period_start": "2024-01-01",
                "period_end": "2024-03-31",
                "include_anomaly_detection": True,
                "include_trend_analysis": True
            }
        }


class FinancialHealthMonitorResponse(BaseModel):
    """财务健康监控响应"""
    monitor_id: str = Field(..., description="监控ID")
    status: str = Field(..., description="监控状态")
    dashboard: Optional[FinancialHealthDashboard] = Field(None, description="健康仪表盘")
    anomalies_detected: List[AnomalyItem] = Field(default_factory=list, description="检测到的异常")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class AnomalyQueryRequest(BaseModel):
    """异常查询请求"""
    tenant_id: str = Field(..., description="租户ID")
    anomaly_types: Optional[List[AnomalyType]] = Field(None, description="异常类型筛选")
    severity_levels: Optional[List[SeverityLevel]] = Field(None, description="严重程度筛选")
    status: Optional[AnomalyStatus] = Field(None, description="状态筛选")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    limit: int = Field(50, ge=1, le=200, description="返回数量")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant-456",
                "anomaly_types": ["revenue_drop", "cost_surge"],
                "severity_levels": ["high", "critical"],
                "limit": 50
            }
        }


class AnomalyQueryResponse(BaseModel):
    """异常查询响应"""
    total_count: int = Field(..., description="总数")
    anomalies: List[AnomalyItem] = Field(default_factory=list, description="异常列表")


class AnomalyActionRequest(BaseModel):
    """异常操作请求"""
    anomaly_id: str = Field(..., description="异常ID")
    action: str = Field(..., description="操作：acknowledge/resolve/dismiss")
    notes: Optional[str] = Field(None, description="备注")
    user_id: str = Field(..., description="用户ID")


class AnomalyActionResponse(BaseModel):
    """异常操作响应"""
    anomaly_id: str = Field(..., description="异常ID")
    action: str = Field(..., description="执行的操作")
    new_status: AnomalyStatus = Field(..., description="新状态")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class TrendAnalysisRequest(BaseModel):
    """趋势分析请求"""
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    metric_names: List[str] = Field(..., description="要分析的指标名称")
    period_type: str = Field(default="monthly", description="期间类型：monthly/quarterly/annual")
    lookback_periods: int = Field(default=12, ge=3, le=36, description="回溯期数")
    include_forecast: bool = Field(default=True, description="是否包含预测")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant-456",
                "user_id": "user-123",
                "metric_names": ["revenue", "profit", "cash_flow"],
                "period_type": "monthly",
                "lookback_periods": 12,
                "include_forecast": True
            }
        }


class TrendPoint(BaseModel):
    """趋势数据点"""
    period: str = Field(..., description="期间")
    value: float = Field(..., description="值")
    formatted_value: str = Field(..., description="格式化值")
    is_forecast: bool = Field(default=False, description="是否为预测值")
    confidence_interval: Optional[Dict[str, float]] = Field(None, description="置信区间")


class TrendAnalysisResult(BaseModel):
    """趋势分析结果"""
    metric_name: str = Field(..., description="指标名称")
    trend_direction: str = Field(..., description="趋势方向：up/down/stable")
    trend_strength: float = Field(..., ge=0.0, le=1.0, description="趋势强度")
    average_value: float = Field(..., description="平均值")
    min_value: float = Field(..., description="最小值")
    max_value: float = Field(..., description="最大值")
    volatility: float = Field(..., description="波动性")
    forecast_values: List[TrendPoint] = Field(default_factory=list, description="预测值")
    historical_values: List[TrendPoint] = Field(default_factory=list, description="历史值")
    insights: List[str] = Field(default_factory=list, description="洞察")


class TrendAnalysisResponse(BaseModel):
    """趋势分析响应"""
    analysis_id: str = Field(..., description="分析ID")
    tenant_id: str = Field(..., description="租户ID")
    period_type: str = Field(..., description="期间类型")
    analysis_results: List[TrendAnalysisResult] = Field(default_factory=list, description="分析结果")
    summary: str = Field(..., description="摘要")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class AlertSubscriptionRequest(BaseModel):
    """预警订阅请求"""
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    alert_types: List[AnomalyType] = Field(..., description="关注的异常类型")
    severity_threshold: SeverityLevel = Field(..., description="严重程度阈值")
    notification_channels: List[str] = Field(
        default=["in_app"],
        description="通知渠道：in_app/email/sms/webhook"
    )
    notification_email: Optional[str] = Field(None, description="通知邮箱")
    notification_webhook: Optional[str] = Field(None, description="通知Webhook")
    frequency: MonitoringFrequency = Field(default=MonitoringFrequency.DAILY, description="通知频率")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant-456",
                "user_id": "user-123",
                "alert_types": ["revenue_drop", "negative_cashflow"],
                "severity_threshold": "high",
                "notification_channels": ["in_app", "email"],
                "notification_email": "cfo@company.com",
                "frequency": "daily"
            }
        }


class AlertSubscriptionResponse(BaseModel):
    """预警订阅响应"""
    subscription_id: str = Field(..., description="订阅ID")
    status: str = Field(..., description="订阅状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    message: str = Field(..., description="状态消息")
