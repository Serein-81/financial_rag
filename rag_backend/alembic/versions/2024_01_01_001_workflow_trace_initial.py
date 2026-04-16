# alembic/versions/2024_01_01_001_workflow_trace_initial.py

"""
工作流追踪数据模型初始迁移

Revision ID: workflow_trace_initial
Revises: latest
Create Date: 2024-01-01

此迁移创建以下表：
- workflow_traces: 工作流追踪主表
- workflow_node_executions: 工作流节点执行记录表
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'workflow_trace_initial'
down_revision = None  # 替换为最新的revision ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workflow_traces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_type', sa.String(100), nullable=False),
        sa.Column('workflow_version', sa.String(50), nullable=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tenant_id', sa.String(50), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('input_data', postgresql.JSON, nullable=True),
        sa.Column('output_data', postgresql.JSON, nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('current_node', sa.String(100), nullable=True),
        sa.Column('total_nodes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_nodes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('checkpointer_type', sa.String(20), nullable=True),
        sa.Column('checkpoint_id', sa.String(100), nullable=True),
        sa.Column('workflow_metadata', postgresql.JSON, nullable=True),
        sa.Column('human_review_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ),
        sa.ForeignKeyConstraint(['human_review_id'], ['review_requests.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_traces_workflow_type', 'workflow_traces', ['workflow_type'])
    op.create_index('ix_workflow_traces_session_id', 'workflow_traces', ['session_id'])
    op.create_index('ix_workflow_traces_tenant_id', 'workflow_traces', ['tenant_id'])
    op.create_index('ix_workflow_traces_user_id', 'workflow_traces', ['user_id'])
    op.create_index('ix_workflow_traces_status', 'workflow_traces', ['status'])
    op.create_index('ix_workflow_traces_tenant_status', 'workflow_traces', ['tenant_id', 'status'])
    op.create_index('ix_workflow_traces_user_created', 'workflow_traces', ['user_id', 'created_at'])
    op.create_index('ix_workflow_traces_created_at', 'workflow_traces', ['created_at'])
    op.create_index('ix_workflow_traces_human_review_id', 'workflow_traces', ['human_review_id'])
    
    op.create_table(
        'workflow_node_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_trace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_trace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('node_name', sa.String(100), nullable=False),
        sa.Column('node_type', sa.String(50), nullable=True),
        sa.Column('execution_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_data', postgresql.JSON, nullable=True),
        sa.Column('output_data', postgresql.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('token_usage', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workflow_trace_id'], ['workflow_traces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_trace_id'], ['agent_traces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_node_executions_workflow_trace_id', 'workflow_node_executions', ['workflow_trace_id'])
    op.create_index('ix_workflow_node_executions_agent_trace_id', 'workflow_node_executions', ['agent_trace_id'])
    op.create_index('ix_workflow_node_executions_trace_order', 'workflow_node_executions', ['workflow_trace_id', 'execution_order'])
    op.create_index('ix_workflow_node_executions_node_name', 'workflow_node_executions', ['node_name'])


def downgrade() -> None:
    op.drop_table('workflow_node_executions')
    op.drop_table('workflow_traces')
