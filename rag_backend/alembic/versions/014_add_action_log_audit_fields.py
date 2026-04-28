"""Add audit fields to user action logs.

Revision ID: 014_add_action_log_audit_fields
Revises: 013_trace_schema_compatibility
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


revision: str = "014_add_action_log_audit_fields"
down_revision: Union[str, None] = "013_trace_schema_compatibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("system_logs", sa.Column("tenant_id", sa.String(length=50), nullable=True))
    op.create_index("ix_system_logs_tenant_id", "system_logs", ["tenant_id"])

    op.add_column("user_action_logs", sa.Column("tenant_id", sa.String(length=50), nullable=True))
    op.add_column(
        "user_action_logs",
        sa.Column("risk_level", sa.String(length=20), nullable=False, server_default="low"),
    )
    op.create_index("ix_user_action_logs_tenant_id", "user_action_logs", ["tenant_id"])
    op.create_index("ix_user_action_logs_risk_level", "user_action_logs", ["risk_level"])
    op.create_index(
        "idx_action_logs_tenant_time",
        "user_action_logs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_action_logs_tenant_risk_time",
        "user_action_logs",
        ["tenant_id", "risk_level", "created_at"],
    )

    op.execute(
        """
        UPDATE user_action_logs AS logs
        SET tenant_id = users.tenant_id
        FROM users
        WHERE logs.user_id = users.id
          AND logs.tenant_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE system_logs AS logs
        SET tenant_id = users.tenant_id
        FROM users
        WHERE logs.user_id = users.id
          AND logs.tenant_id IS NULL
        """
    )
    op.alter_column("user_action_logs", "risk_level", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_action_logs_tenant_risk_time", table_name="user_action_logs")
    op.drop_index("idx_action_logs_tenant_time", table_name="user_action_logs")
    op.drop_index("ix_user_action_logs_risk_level", table_name="user_action_logs")
    op.drop_index("ix_user_action_logs_tenant_id", table_name="user_action_logs")
    op.drop_column("user_action_logs", "risk_level")
    op.drop_column("user_action_logs", "tenant_id")
    op.drop_index("ix_system_logs_tenant_id", table_name="system_logs")
    op.drop_column("system_logs", "tenant_id")
