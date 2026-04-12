"""Initial policy tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'policies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('policy_id', sa.String(100), nullable=False, unique=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('summary', sa.String(2000), nullable=True),
        sa.Column('source_name', sa.String(100), nullable=True),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('published_date', sa.DateTime(), nullable=True),
        sa.Column('effective_date', sa.DateTime(), nullable=True),
        sa.Column('expiry_date', sa.DateTime(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=True, default='medium'),
        sa.Column('status', sa.String(20), nullable=True, default='active'),
        sa.Column('industries', postgresql.ARRAY(sa.String(100)), nullable=True, default=[]),
        sa.Column('regions', postgresql.ARRAY(sa.String(100)), nullable=True, default=[]),
        sa.Column('scales', postgresql.ARRAY(sa.String(50)), nullable=True, default=[]),
        sa.Column('tax_types', postgresql.ARRAY(sa.String(100)), nullable=True, default=[]),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), nullable=True, default=[]),
        sa.Column('embedding', sa.LargeBinary(), nullable=True),
        sa.Column('meta_info', postgresql.JSON(), nullable=True),
        sa.Column('view_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('tenant_id', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('policy_id')
    )
    
    op.create_index('idx_policies_status', 'policies', ['status'])
    op.create_index('idx_policies_priority', 'policies', ['priority'])
    op.create_index('idx_policies_published_date', 'policies', ['published_date'])
    op.create_index('idx_policies_tenant_id', 'policies', ['tenant_id'])
    
    op.create_table(
        'policy_relations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_policy_id', sa.UUID(), nullable=False),
        sa.Column('target_policy_id', sa.UUID(), nullable=False),
        sa.Column('relation_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('tenant_id', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_policy_id'], ['policies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_policy_id'], ['policies.id'], ondelete='CASCADE')
    )
    
    op.create_index('idx_policy_relations_source', 'policy_relations', ['source_policy_id'])
    op.create_index('idx_policy_relations_target', 'policy_relations', ['target_policy_id'])
    op.create_index('idx_policy_relations_type', 'policy_relations', ['relation_type'])
    
    op.create_table(
        'enterprise_policy_matches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('enterprise_id', sa.String(100), nullable=False),
        sa.Column('policy_id', sa.UUID(), nullable=False),
        sa.Column('match_score', sa.Float(), nullable=True),
        sa.Column('match_status', sa.String(20), nullable=True, default='pending'),
        sa.Column('notification_status', sa.String(20), nullable=True, default='pending'),
        sa.Column('match_reasons', postgresql.ARRAY(sa.String(500)), nullable=True, default=[]),
        sa.Column('acknowledged', sa.Boolean(), nullable=True, default=False),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('meta_info', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE')
    )
    
    op.create_index('idx_matches_enterprise', 'enterprise_policy_matches', ['enterprise_id'])
    op.create_index('idx_matches_policy', 'enterprise_policy_matches', ['policy_id'])
    op.create_index('idx_matches_notification_status', 'enterprise_policy_matches', ['notification_status'])
    op.create_index('idx_matches_acknowledged', 'enterprise_policy_matches', ['acknowledged'])
    
    op.create_table(
        'update_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_name', sa.String(100), nullable=True),
        sa.Column('update_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('policies_added', sa.Integer(), nullable=True, default=0),
        sa.Column('policies_updated', sa.Integer(), nullable=True, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('tenant_id', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_update_history_source', 'update_history', ['source_name'])
    op.create_index('idx_update_history_status', 'update_history', ['status'])
    op.create_index('idx_update_history_started', 'update_history', ['started_at'])


def downgrade() -> None:
    op.drop_table('update_history')
    op.drop_table('enterprise_policy_matches')
    op.drop_table('policy_relations')
    op.drop_table('policies')
