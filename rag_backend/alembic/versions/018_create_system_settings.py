"""create system_settings table

Revision ID: 018_create_system_settings
Revises: 017_add_agent_trace_model_name
Create Date: 2026-05-30

部署级键值配置表，存放 Embedding / Rerank 等不适合按租户隔离的全局模型配置。
幂等实现，可与手工 SQL 共存。
"""

from typing import Sequence, Union

from alembic import op


revision: str = "018_create_system_settings"
down_revision: Union[str, None] = "017_add_agent_trace_model_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            key VARCHAR(100) PRIMARY KEY,
            value JSONB,
            updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS system_settings")
