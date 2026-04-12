"""Add enterprise profile fields to tenant_settings

Revision ID: 002
Revises: 001
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add enterprise profile fields to tenant_settings table
    op.add_column(
        'tenant_settings',
        sa.Column('industry', sa.String(100), nullable=True, index=True)
    )
    op.add_column(
        'tenant_settings',
        sa.Column('region', sa.String(100), nullable=True, index=True)
    )
    op.add_column(
        'tenant_settings',
        sa.Column('scale', sa.String(50), nullable=True, index=True)
    )
    op.add_column(
        'tenant_settings',
        sa.Column('tax_types', postgresql.ARRAY(sa.String(100)), nullable=True, server_default='{}')
    )


def downgrade() -> None:
    op.drop_column('tenant_settings', 'tax_types')
    op.drop_column('tenant_settings', 'scale')
    op.drop_column('tenant_settings', 'region')
    op.drop_column('tenant_settings', 'industry')
