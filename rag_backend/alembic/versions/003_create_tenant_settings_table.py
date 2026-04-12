"""Create tenant_settings table

Revision ID: 003
Revises: 001
Create Date: 2026-04-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenant_settings',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.String(50), nullable=False, unique=True),
        sa.Column('company_name', sa.String(200), nullable=False),
        sa.Column('company_logo', sa.String(500), nullable=True),
        sa.Column('company_description', sa.Text(), nullable=True),
        sa.Column('company_website', sa.String(500), nullable=True),
        sa.Column('company_address', sa.String(500), nullable=True),
        sa.Column('company_phone', sa.String(50), nullable=True),
        sa.Column('company_email', sa.String(255), nullable=True),
        sa.Column('admin_name', sa.String(100), nullable=True),
        sa.Column('admin_email', sa.String(255), nullable=True),
        sa.Column('admin_phone', sa.String(50), nullable=True),
        sa.Column('max_users', sa.Integer(), nullable=True, server_default='10'),
        sa.Column('max_storage_gb', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('max_knowledge_bases', sa.Integer(), nullable=True, server_default='10'),
        sa.Column('max_documents', sa.Integer(), nullable=True, server_default='1000'),
        sa.Column('max_monthly_requests', sa.Integer(), nullable=True),
        sa.Column('enable_group_chat', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('enable_multi_agent', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('enable_knowledge_graph', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enable_human_review', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('enable_audit', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enable_tax_report', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enable_financial_data', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('primary_color', sa.String(20), nullable=True, server_default='#1890ff'),
        sa.Column('secondary_color', sa.String(20), nullable=True),
        sa.Column('custom_css', sa.Text(), nullable=True),
        sa.Column('custom_footer', sa.Text(), nullable=True),
        sa.Column('email_notification', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('system_notification', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('notification_email', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_trial', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('trial_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extra_settings', postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_tenant_settings_tenant_id', 'tenant_settings', ['tenant_id'])
    op.create_index('idx_tenant_settings_industry', 'tenant_settings', ['industry'])
    op.create_index('idx_tenant_settings_region', 'tenant_settings', ['region'])


def downgrade() -> None:
    op.drop_index('idx_tenant_settings_region', table_name='tenant_settings')
    op.drop_index('idx_tenant_settings_industry', table_name='tenant_settings')
    op.drop_index('idx_tenant_settings_tenant_id', table_name='tenant_settings')
    op.drop_table('tenant_settings')
