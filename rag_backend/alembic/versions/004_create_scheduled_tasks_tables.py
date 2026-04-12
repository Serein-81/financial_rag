"""Create scheduled_tasks, task_execution_logs, task_notifications tables

Revision ID: 004
Revises: 003
Create Date: 2026-04-05 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_tasks',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('task_id', sa.String(100), nullable=False),
        sa.Column('user_id', postgresql.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('frequency', sa.String(20), nullable=False),
        sa.Column('next_run_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('task_params', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('notification_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notification_channels', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduled_tasks_task_id', 'scheduled_tasks', ['task_id'], unique=True)
    op.create_index('ix_scheduled_tasks_user_id', 'scheduled_tasks', ['user_id'])
    op.create_index('ix_scheduled_tasks_tenant_id', 'scheduled_tasks', ['tenant_id'])
    op.create_index('ix_scheduled_tasks_task_type', 'scheduled_tasks', ['task_type'])
    op.create_index('ix_scheduled_tasks_next_run_time', 'scheduled_tasks', ['next_run_time'])
    op.create_index('ix_scheduled_tasks_status', 'scheduled_tasks', ['status'])
    op.create_foreign_key('fk_scheduled_tasks_user_id', 'scheduled_tasks', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    op.create_table(
        'task_execution_logs',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('task_id', sa.String(100), nullable=False),
        sa.Column('scheduled_task_id', postgresql.UUID(), nullable=True),
        sa.Column('user_id', postgresql.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('execution_type', sa.String(20), nullable=False, server_default='scheduled'),
        sa.Column('triggered_manually', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_task_execution_logs_task_id', 'task_execution_logs', ['task_id'])
    op.create_index('ix_task_execution_logs_scheduled_task_id', 'task_execution_logs', ['scheduled_task_id'])
    op.create_index('ix_task_execution_logs_user_id', 'task_execution_logs', ['user_id'])
    op.create_index('ix_task_execution_logs_tenant_id', 'task_execution_logs', ['tenant_id'])
    op.create_index('ix_task_execution_logs_status', 'task_execution_logs', ['status'])
    op.create_foreign_key('fk_task_execution_logs_scheduled_task_id', 'task_execution_logs', 'scheduled_tasks', ['scheduled_task_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_task_execution_logs_user_id', 'task_execution_logs', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    op.create_table(
        'task_notifications',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('task_id', postgresql.UUID(), nullable=True),
        sa.Column('execution_log_id', postgresql.UUID(), nullable=True),
        sa.Column('user_id', postgresql.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('channels', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_task_notifications_task_id', 'task_notifications', ['task_id'])
    op.create_index('ix_task_notifications_execution_log_id', 'task_notifications', ['execution_log_id'])
    op.create_index('ix_task_notifications_user_id', 'task_notifications', ['user_id'])
    op.create_index('ix_task_notifications_tenant_id', 'task_notifications', ['tenant_id'])
    op.create_index('ix_task_notifications_status', 'task_notifications', ['status'])
    op.create_foreign_key('fk_task_notifications_task_id', 'task_notifications', 'scheduled_tasks', ['task_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_task_notifications_execution_log_id', 'task_notifications', 'task_execution_logs', ['execution_log_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_task_notifications_user_id', 'task_notifications', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_table('task_notifications')
    op.drop_table('task_execution_logs')
    op.drop_table('scheduled_tasks')
