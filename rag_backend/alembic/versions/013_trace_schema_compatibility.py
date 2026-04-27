"""Add compatible trace schema columns and indexes.

Revision ID: 013_trace_schema_compatibility
Revises: 012_create_agent_task_tables
Create Date: 2026-04-27
"""

from alembic import op
from typing import Sequence, Union


revision: str = "013_trace_schema_compatibility"
down_revision: Union[str, None] = "012_create_agent_task_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_traces (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tenant_id VARCHAR(50) NOT NULL,
            session_id UUID NULL REFERENCES chat_sessions(id),
            message_id UUID NULL REFERENCES chat_messages(id),
            agent_type VARCHAR NOT NULL,
            user_query TEXT NOT NULL,
            final_answer TEXT NULL,
            langsmith_run_id VARCHAR NULL,
            total_iterations INTEGER DEFAULT 0,
            total_time DOUBLE PRECISION DEFAULT 0.0,
            tool_calls_count INTEGER DEFAULT 0,
            status VARCHAR DEFAULT 'running',
            error_message TEXT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            completed_at TIMESTAMPTZ NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_steps (
            id UUID PRIMARY KEY,
            trace_id UUID NOT NULL REFERENCES agent_traces(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tenant_id VARCHAR(50) NOT NULL,
            step_number INTEGER NOT NULL,
            step_type VARCHAR NOT NULL,
            content TEXT NOT NULL,
            tool_name VARCHAR NULL,
            tool_input JSONB NULL,
            tool_output TEXT NULL,
            tool_duration DOUBLE PRECISION NULL,
            confidence DOUBLE PRECISION NULL,
            metadata JSONB NULL,
            step_metadata JSON NULL,
            timestamp DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_call_traces (
            id UUID PRIMARY KEY,
            trace_id UUID NULL REFERENCES agent_traces(id),
            parent_call_id UUID NULL REFERENCES tool_call_traces(id),
            user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
            tenant_id VARCHAR(50) NULL,
            session_id UUID NULL REFERENCES chat_sessions(id) ON DELETE SET NULL,
            tool_name VARCHAR NOT NULL,
            tool_type VARCHAR DEFAULT 'function',
            input_params JSONB NULL,
            output_result TEXT NULL,
            start_time DOUBLE PRECISION NOT NULL,
            end_time DOUBLE PRECISION NULL,
            duration DOUBLE PRECISION NULL,
            status VARCHAR DEFAULT 'running',
            error_message TEXT NULL,
            metadata JSONB NULL,
            tool_metadata JSON NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    op.execute("ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS langsmith_run_id VARCHAR")
    op.execute("ALTER TABLE tool_call_traces ADD COLUMN IF NOT EXISTS user_id UUID")
    op.execute("ALTER TABLE tool_call_traces ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50)")
    op.execute("ALTER TABLE tool_call_traces ADD COLUMN IF NOT EXISTS session_id UUID")

    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_traces_user_id ON agent_traces(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_traces_tenant_id ON agent_traces(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_steps_user_id ON agent_steps(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_steps_tenant_id ON agent_steps(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tool_call_traces_user_id ON tool_call_traces(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tool_call_traces_tenant_id ON tool_call_traces(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tool_call_traces_session_id ON tool_call_traces(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tool_call_traces_trace_id ON tool_call_traces(trace_id)")

    op.execute(
        """
        UPDATE tool_call_traces t
        SET
            user_id = COALESCE(t.user_id, a.user_id),
            tenant_id = COALESCE(t.tenant_id, a.tenant_id),
            session_id = COALESCE(t.session_id, a.session_id)
        FROM agent_traces a
        WHERE t.trace_id = a.id
          AND (
              t.user_id IS NULL
              OR t.tenant_id IS NULL
              OR t.session_id IS NULL
          )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tool_call_traces_trace_id")
    op.execute("DROP INDEX IF EXISTS ix_tool_call_traces_session_id")
    op.execute("DROP INDEX IF EXISTS ix_tool_call_traces_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_tool_call_traces_user_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_steps_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_steps_user_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_traces_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_traces_user_id")
    op.execute("ALTER TABLE tool_call_traces DROP COLUMN IF EXISTS session_id")
    op.execute("ALTER TABLE tool_call_traces DROP COLUMN IF EXISTS tenant_id")
    op.execute("ALTER TABLE tool_call_traces DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE agent_traces DROP COLUMN IF EXISTS langsmith_run_id")
