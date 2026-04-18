"""Create contract review tables

Revision ID: 008
Revises: 007
Create Date: 2026-04-18 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum


revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class ContractType(str, enum.Enum):
    purchase = "purchase"
    sales = "sales"
    service = "service"
    lease = "lease"
    employment = "employment"
    partnership = "partnership"
    loan = "loan"
    other = "other"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    approved = "approved"
    rejected = "rejected"
    needs_revision = "needs_revision"


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


def upgrade() -> None:
    op.create_table(
        'contract_review_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('contract_name', sa.String(500), nullable=False),
        sa.Column('contract_type', sa.Enum(ContractType, name='contracttype'), nullable=True),
        sa.Column('counterparty', sa.String(255), nullable=True),
        sa.Column('contract_value', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True, default='CNY'),
        sa.Column('original_text', sa.Text, nullable=True),
        sa.Column('review_status', sa.Enum(ReviewStatus, name='reviewstatus'), nullable=False),
        sa.Column('overall_risk_score', sa.Float(), nullable=True),
        sa.Column('overall_risk_level', sa.Enum(RiskLevel, name='risklevel'), nullable=True),
        sa.Column('basic_analysis', JSONB, nullable=True),
        sa.Column('parties_info', JSONB, nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expiration_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('termination_conditions', JSONB, nullable=True),
        sa.Column('clauses_analysis', JSONB, nullable=True),
        sa.Column('risk_clauses', JSONB, nullable=True),
        sa.Column('unfavorable_clauses', JSONB, nullable=True),
        sa.Column('compliance_checks', JSONB, nullable=True),
        sa.Column('comparison_result', JSONB, nullable=True),
        sa.Column('suggestions', JSONB, nullable=True),
        sa.Column('recommended_revisions', JSONB, nullable=True),
        sa.Column('ai_analysis_summary', sa.Text, nullable=True),
        sa.Column('pdf_path', sa.String(1000), nullable=True),
        sa.Column('review_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_contract_review_reports_user_id', 'contract_review_reports', ['user_id'])
    op.create_index('ix_contract_review_reports_tenant_id', 'contract_review_reports', ['tenant_id'])
    op.create_index('ix_contract_review_reports_created_at', 'contract_review_reports', ['created_at'])
    op.create_index('ix_contract_review_reports_review_status', 'contract_review_reports', ['review_status'])

    op.create_table(
        'contract_clauses',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('report_id', UUID(as_uuid=True), sa.ForeignKey('contract_review_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('clause_type', sa.String(50), nullable=False),
        sa.Column('clause_title', sa.String(255), nullable=True),
        sa.Column('clause_text', sa.Text, nullable=False),
        sa.Column('original_position', sa.Integer(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.Enum(RiskLevel, name='risklevel'), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('is_standard', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_controversial', sa.Boolean(), nullable=True, default=False),
        sa.Column('needs_attention', sa.Boolean(), nullable=True, default=False),
        sa.Column('analysis', JSONB, nullable=True),
        sa.Column('suggestions', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_contract_clauses_report_id', 'contract_clauses', ['report_id'])
    op.create_index('ix_contract_clauses_clause_type', 'contract_clauses', ['clause_type'])

    op.create_table(
        'contract_comparison_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('comparison_name', sa.String(255), nullable=False),
        sa.Column('contract1_id', UUID(as_uuid=True), sa.ForeignKey('contract_review_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract2_id', UUID(as_uuid=True), sa.ForeignKey('contract_review_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('comparison_result', JSONB, nullable=True),
        sa.Column('differences', JSONB, nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_contract_comparison_history_user_id', 'contract_comparison_history', ['user_id'])
    op.create_index('ix_contract_comparison_history_tenant_id', 'contract_comparison_history', ['tenant_id'])

    op.create_table(
        'contract_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('contract_type', sa.Enum(ContractType, name='contracttype'), nullable=False),
        sa.Column('template_content', sa.Text, nullable=False),
        sa.Column('clauses_library', JSONB, nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True, default=0),
        sa.Column('is_public', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_contract_templates_tenant_id', 'contract_templates', ['tenant_id'])


def downgrade() -> None:
    op.drop_table('contract_templates')
    op.drop_table('contract_comparison_history')
    op.drop_table('contract_clauses')
    op.drop_table('contract_review_reports')
    op.execute('DROP TYPE IF EXISTS risklevel')
    op.execute('DROP TYPE IF EXISTS reviewstatus')
    op.execute('DROP TYPE IF EXISTS contracttype')
