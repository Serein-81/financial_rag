"""创建 Agent 任务状态表

用于 LangGraph 状态持久化和前端水合

Revision ID: 012_create_agent_task_tables
Revises: 011_migrate_document_chunks_embedding
Create Date: 2025-04-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '012_create_agent_task_tables'
down_revision = '011_migrate_document_chunks_embedding'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE IF NOT EXISTS task_status_enum AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled', 'interrupted')")
    op.execute("CREATE TYPE IF NOT EXISTS task_priority_enum AS ENUM ('low', 'normal', 'high', 'urgent')")
    
    op.create_table(
        'agent_task_status',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('thread_id', sa.String(255), nullable=False, index=True),
        sa.Column('tenant_id', sa.String(100), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('request_id', sa.String(100), nullable=True, index=True),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('task_name', sa.String(255), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', 'cancelled', 'interrupted', name='task_status_enum', create_type=False), default='pending', nullable=False),
        sa.Column('priority', postgresql.ENUM('low', 'normal', 'high', 'urgent', name='task_priority_enum', create_type=False), default='normal', nullable=False),
        sa.Column('user_query', sa.Text, nullable=True),
        sa.Column('final_response', sa.Text, nullable=True),
        sa.Column('current_node', sa.String(100), nullable=True),
        sa.Column('progress_percent', sa.Integer, default=0),
        sa.Column('progress_message', sa.String(500), nullable=True),
        sa.Column('specialist_progress', postgresql.JSONB, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('execution_time_ms', sa.Float, default=0.0),
        sa.Column('arq_job_id', sa.String(100), nullable=True, index=True),
        sa.Column('checkpoint_id', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_task_status_tenant_created', 'agent_task_status', ['tenant_id', 'created_at'])
    op.create_index('idx_task_status_user', 'agent_task_status', ['user_id', 'status'])
    op.create_index('idx_task_status_thread', 'agent_task_status', ['thread_id', 'status'])
    
    op.create_table(
        'agent_task_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', sa.String(100), sa.ForeignKey('agent_task_status.task_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tenant_id', sa.String(100), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', postgresql.JSONB, nullable=True),
        sa.Column('node_name', sa.String(100), nullable=True),
        sa.Column('event_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_task_event_task', 'agent_task_events', ['task_id', 'created_at'])
    
    op.create_table(
        'agent_task_checkpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', sa.String(100), sa.ForeignKey('agent_task_status.task_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('checkpoint_id', sa.String(255), nullable=False),
        sa.Column('parent_checkpoint_id', sa.String(255), nullable=True),
        sa.Column('node_name', sa.String(100), nullable=True),
        sa.Column('state_data', postgresql.JSONB, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_task_checkpoint_task', 'agent_task_checkpoints', ['task_id', 'created_at'])
    op.create_index('idx_task_checkpoint_parent', 'agent_task_checkpoints', ['parent_checkpoint_id'])
    
    op.create_table(
        'langgraph_checkpoints',
        sa.Column('thread_id', sa.String(255), primary_key=True),
        sa.Column('checkpoint_id', sa.String(255), primary_key=True),
        sa.Column('parent_checkpoint_id', sa.String(255), nullable=True),
        sa.Column('checkpoint_data', postgresql.JSONB, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_lg_checkpoint_thread', 'langgraph_checkpoints', ['thread_id'])
    op.create_index('idx_lg_checkpoint_updated', 'langgraph_checkpoints', ['updated_at'])
    op.create_index('idx_lg_checkpoint_parent', 'langgraph_checkpoints', ['parent_checkpoint_id'])


def downgrade() -> None:
    op.drop_table('langgraph_checkpoints')
    op.drop_table('agent_task_checkpoints')
    op.drop_table('agent_task_events')
    op.drop_table('agent_task_status')
    op.execute('DROP TYPE IF EXISTS task_status_enum')
    op.execute('DROP TYPE IF EXISTS task_priority_enum')