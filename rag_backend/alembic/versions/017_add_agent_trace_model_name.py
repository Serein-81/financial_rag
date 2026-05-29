"""add model_name to agent_traces

Revision ID: 017_add_agent_trace_model_name
Revises: 016_create_feedback_tables
Create Date: 2026-05-29

记录每次 Agent 执行实际使用的 LLM 模型名，用于管理员「使用概览」展示
最近对话模型与各模型调用次数。幂等实现，可与手工 SQL 共存。
"""

from typing import Sequence, Union

from alembic import op


revision: str = "017_add_agent_trace_model_name"
down_revision: Union[str, None] = "016_create_feedback_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS model_name VARCHAR(200)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_traces_model_name "
        "ON agent_traces (model_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_traces_model_name")
    op.execute("ALTER TABLE agent_traces DROP COLUMN IF EXISTS model_name")
