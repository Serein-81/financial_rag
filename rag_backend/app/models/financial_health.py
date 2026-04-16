"""
财务健康报告数据库模型
存储定期财务健康监控报告数据
"""

import uuid
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
import enum


class ReportPeriod(str, enum.Enum):
    """报告周期"""
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class HealthStatus(str, enum.Enum):
    """健康状态"""
    healthy = "healthy"
    warning = "warning"
    critical = "critical"
    caution = "caution"
    unknown = "unknown"
    excellent = "excellent"


class FinancialHealthReport(Base):
    """
    财务健康报告模型
    
    存储定期生成的财务健康分析报告
    """
    __tablename__ = "financial_health_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    report_name = Column(String(255), nullable=False)
    report_period = Column(SQLEnum(ReportPeriod), nullable=False, default=ReportPeriod.monthly)

    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    overall_health_score = Column(Float, nullable=True)
    health_status = Column(SQLEnum(HealthStatus), nullable=True, default=HealthStatus.unknown)

    revenue_summary = Column(JSONB, nullable=True)
    expense_summary = Column(JSONB, nullable=True)
    profit_summary = Column(JSONB, nullable=True)
    cash_flow_summary = Column(JSONB, nullable=True)

    financial_metrics = Column(JSONB, nullable=True)
    trend_indicators = Column(JSONB, nullable=True)
    anomaly_detections = Column(JSONB, nullable=True)

    risk_assessments = Column(JSONB, nullable=True)
    recommendations = Column(JSONB, nullable=True)

    revenue_data = Column(JSONB, nullable=True)
    expense_data = Column(JSONB, nullable=True)

    generated_by = Column(String(50), default="system")
    source_data_description = Column(Text, nullable=True)

    status = Column(String(20), default="completed", index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<FinancialHealthReport(id={self.id}, tenant_id={self.tenant_id}, status={self.status})>"

    @property
    def period_days(self):
        """计算报告周期天数"""
        if self.period_start and self.period_end:
            return (self.period_end - self.period_start).days
        return 0


class FinancialAnomalyRecord(Base):
    """
    财务异常记录模型
    
    存储检测到的财务异常事件
    """
    __tablename__ = "financial_anomaly_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    report_id = Column(UUID(as_uuid=True), ForeignKey("financial_health_reports.id", ondelete="CASCADE"), nullable=True, index=True)

    anomaly_type = Column(String(50), nullable=False, index=True)
    anomaly_category = Column(String(50), nullable=True)

    severity = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    detected_value = Column(Float, nullable=True)
    expected_value = Column(Float, nullable=True)
    deviation = Column(Float, nullable=True)
    deviation_percentage = Column(Float, nullable=True)

    affected_accounts = Column(JSONB, nullable=True)
    related_transactions = Column(JSONB, nullable=True)

    recommended_actions = Column(JSONB, nullable=True)

    status = Column(String(20), default="detected", index=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<FinancialAnomalyRecord(id={self.id}, type={self.anomaly_type}, severity={self.severity})>"


class FinancialTrendData(Base):
    """
    财务趋势数据模型
    
    存储财务指标的历史趋势数据
    """
    __tablename__ = "financial_trend_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    metric_name = Column(String(100), nullable=False, index=True)
    metric_category = Column(String(50), nullable=True)

    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)

    record_date = Column(DateTime(timezone=True), nullable=False, index=True)
    period_type = Column(String(20), nullable=False)

    meta_data = Column(JSONB, nullable=True)

    source = Column(String(50), default="calculated")

    created_at = Column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self):
        return f"<FinancialTrendData(id={self.id}, metric={self.metric_name}, value={self.metric_value})>"


class FinancialThreshold(Base):
    """
    财务阈值配置模型
    
    存储各类财务指标的告警阈值配置
    """
    __tablename__ = "financial_thresholds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(String(50), nullable=False, index=True)

    metric_name = Column(String(100), nullable=False, index=True)
    metric_category = Column(String(50), nullable=True)

    warning_threshold = Column(Float, nullable=True)
    critical_threshold = Column(Float, nullable=True)

    comparison_operator = Column(String(10), default=">")

    enabled = Column(Boolean, default=True)

    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<FinancialThreshold(id={self.id}, metric={self.metric_name})>"
