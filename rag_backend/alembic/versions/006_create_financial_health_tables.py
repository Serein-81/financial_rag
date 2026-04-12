"""Create financial health tables

Revision ID: 006
Revises: 005
Create Date: 2026-04-11 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum


revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class ReportPeriod(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class HealthStatus(str, enum.Enum):
    healthy = "healthy"
    warning = "warning"
    critical = "critical"
    caution = "caution"
    unknown = "unknown"
    excellent = "excellent"


def upgrade() -> None:
    op.create_table(
        'financial_health_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('report_name', sa.String(255), nullable=False),
        sa.Column('report_period', sa.Enum(ReportPeriod, name='reportperiod'), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('overall_health_score', sa.Float(), nullable=True),
        sa.Column('health_status', sa.Enum(HealthStatus, name='healthstatus'), nullable=True),
        sa.Column('revenue_summary', JSONB, nullable=True),
        sa.Column('expense_summary', JSONB, nullable=True),
        sa.Column('profit_summary', JSONB, nullable=True),
        sa.Column('cash_flow_summary', JSONB, nullable=True),
        sa.Column('financial_metrics', JSONB, nullable=True),
        sa.Column('trend_indicators', JSONB, nullable=True),
        sa.Column('anomaly_detections', JSONB, nullable=True),
        sa.Column('risk_assessments', JSONB, nullable=True),
        sa.Column('recommendations', JSONB, nullable=True),
        sa.Column('revenue_data', JSONB, nullable=True),
        sa.Column('expense_data', JSONB, nullable=True),
        sa.Column('generated_by', sa.String(50), default='system'),
        sa.Column('source_data_description', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_financial_health_reports_user_id', 'financial_health_reports', ['user_id'])
    op.create_index('ix_financial_health_reports_tenant_id', 'financial_health_reports', ['tenant_id'])
    op.create_index('ix_financial_health_reports_status', 'financial_health_reports', ['status'])
    op.create_index('ix_financial_health_reports_created_at', 'financial_health_reports', ['created_at'])

    op.create_table(
        'financial_anomaly_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('report_id', UUID(as_uuid=True), sa.ForeignKey('financial_health_reports.id', ondelete='CASCADE'), nullable=True),
        sa.Column('anomaly_type', sa.String(50), nullable=False),
        sa.Column('anomaly_category', sa.String(50), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('detected_value', sa.Float(), nullable=True),
        sa.Column('expected_value', sa.Float(), nullable=True),
        sa.Column('deviation', sa.Float(), nullable=True),
        sa.Column('deviation_percentage', sa.Float(), nullable=True),
        sa.Column('affected_accounts', JSONB, nullable=True),
        sa.Column('related_transactions', JSONB, nullable=True),
        sa.Column('recommended_actions', JSONB, nullable=True),
        sa.Column('status', sa.String(20), default='detected'),
        sa.Column('acknowledged', sa.Boolean(), default=False),
        sa.Column('acknowledged_by', UUID(as_uuid=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_financial_anomaly_records_user_id', 'financial_anomaly_records', ['user_id'])
    op.create_index('ix_financial_anomaly_records_tenant_id', 'financial_anomaly_records', ['tenant_id'])
    op.create_index('ix_financial_anomaly_records_report_id', 'financial_anomaly_records', ['report_id'])
    op.create_index('ix_financial_anomaly_records_anomaly_type', 'financial_anomaly_records', ['anomaly_type'])
    op.create_index('ix_financial_anomaly_records_status', 'financial_anomaly_records', ['status'])
    op.create_index('ix_financial_anomaly_records_created_at', 'financial_anomaly_records', ['created_at'])

    op.create_table(
        'financial_trend_data',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_category', sa.String(50), nullable=True),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('metric_unit', sa.String(20), nullable=True),
        sa.Column('record_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('meta_data', JSONB, nullable=True),
        sa.Column('source', sa.String(50), default='calculated'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_financial_trend_data_user_id', 'financial_trend_data', ['user_id'])
    op.create_index('ix_financial_trend_data_tenant_id', 'financial_trend_data', ['tenant_id'])
    op.create_index('ix_financial_trend_data_metric_name', 'financial_trend_data', ['metric_name'])
    op.create_index('ix_financial_trend_data_record_date', 'financial_trend_data', ['record_date'])
    op.create_index('ix_financial_trend_data_created_at', 'financial_trend_data', ['created_at'])

    op.create_table(
        'financial_thresholds',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_category', sa.String(50), nullable=True),
        sa.Column('warning_threshold', sa.Float(), nullable=True),
        sa.Column('critical_threshold', sa.Float(), nullable=True),
        sa.Column('comparison_operator', sa.String(10), default='>'),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_financial_thresholds_tenant_id', 'financial_thresholds', ['tenant_id'])
    op.create_index('ix_financial_thresholds_metric_name', 'financial_thresholds', ['metric_name'])


def downgrade() -> None:
    op.drop_table('financial_thresholds')
    op.drop_table('financial_trend_data')
    op.drop_table('financial_anomaly_records')
    op.drop_table('financial_health_reports')
    op.execute('DROP TYPE IF EXISTS healthstatus')
    op.execute('DROP TYPE IF EXISTS reportperiod')
