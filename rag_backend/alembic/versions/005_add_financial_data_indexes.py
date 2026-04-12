"""Add composite indexes for financial data queries

Revision ID: 005
Revises: 004
Create Date: 2026-04-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_user_financial_data_lookup',
        'user_financial_data',
        ['user_id', 'tenant_id', 'fiscal_year', 'period_type'],
        unique=False
    )
    op.create_index(
        'ix_user_financial_data_tenant_year',
        'user_financial_data',
        ['tenant_id', 'fiscal_year'],
        unique=False
    )
    op.create_index(
        'ix_user_financial_data_user_year',
        'user_financial_data',
        ['user_id', 'fiscal_year'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_user_financial_data_lookup', 'user_financial_data')
    op.drop_index('ix_user_financial_data_tenant_year', 'user_financial_data')
    op.drop_index('ix_user_financial_data_user_year', 'user_financial_data')
