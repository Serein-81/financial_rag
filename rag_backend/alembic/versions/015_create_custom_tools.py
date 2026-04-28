"""create custom tools table

Revision ID: 015_create_custom_tools
Revises: 014_add_action_log_audit_fields
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "015_create_custom_tools"
down_revision: Union[str, None] = "014_add_action_log_audit_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_tools",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("runtime_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("safety_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_code", sa.Text(), nullable=True),
        sa.Column("agent_id", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("tenant_id", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_tools_agent_id", "custom_tools", ["agent_id"], unique=False)
    op.create_index("ix_custom_tools_created_by", "custom_tools", ["created_by"], unique=False)
    op.create_index("ix_custom_tools_enabled", "custom_tools", ["enabled"], unique=False)
    op.create_index("ix_custom_tools_kind", "custom_tools", ["kind"], unique=False)
    op.create_index("ix_custom_tools_name", "custom_tools", ["name"], unique=False)
    op.create_index("ix_custom_tools_status", "custom_tools", ["status"], unique=False)
    op.create_index("ix_custom_tools_tenant_id", "custom_tools", ["tenant_id"], unique=False)
    op.create_index(
        "ix_custom_tools_tenant_name_version",
        "custom_tools",
        ["tenant_id", "name", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_custom_tools_tenant_name_version", table_name="custom_tools")
    op.drop_index("ix_custom_tools_tenant_id", table_name="custom_tools")
    op.drop_index("ix_custom_tools_status", table_name="custom_tools")
    op.drop_index("ix_custom_tools_name", table_name="custom_tools")
    op.drop_index("ix_custom_tools_kind", table_name="custom_tools")
    op.drop_index("ix_custom_tools_enabled", table_name="custom_tools")
    op.drop_index("ix_custom_tools_created_by", table_name="custom_tools")
    op.drop_index("ix_custom_tools_agent_id", table_name="custom_tools")
    op.drop_table("custom_tools")
