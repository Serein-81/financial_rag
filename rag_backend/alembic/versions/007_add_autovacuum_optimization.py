"""Add autovacuum and storage optimization for high-write tables

Revision ID: 007_add_autovacuum_optimization
Revises: 006_create_financial_health_tables
Create Date: 2025-01-15

针对高频写入表进行PostgreSQL存储参数优化：
- 降低autovacuum触发阈值，防止表膨胀
- 设置fillfactor为UPDATE预留空间
- 调整autovacuum成本延迟，提高清理频率

优化表：
- agent_traces: Agent追踪主表（高频写入）
- agent_steps: Agent步骤表（高频写入）
- workflow_traces: 工作流追踪表（中等写入）
- workflow_node_executions: 工作流节点执行表（中等写入）
- document_chunks: 文档分块表（批量写入为主）
"""

from alembic import op
from typing import Sequence, Union

revision: str = '007_add_autovacuum_optimization'
down_revision: Union[str, None] = '006_create_financial_health_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # 高频写入表优化（Agent追踪）
    # ============================================
    op.execute("""
        ALTER TABLE agent_traces SET (
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_scale_factor = 0.05,
            autovacuum_vacuum_cost_delay = 2,
            fillfactor = 80
        )
    """)
    
    op.execute("""
        ALTER TABLE agent_steps SET (
            autovacuum_vacuum_scale_factor = 0.01,
            autovacuum_analyze_scale_factor = 0.05,
            autovacuum_vacuum_cost_delay = 2,
            fillfactor = 80
        )
    """)
    
    # ============================================
    # 中等写入表优化（工作流追踪）
    # ============================================
    op.execute("""
        ALTER TABLE workflow_traces SET (
            autovacuum_vacuum_scale_factor = 0.05,
            autovacuum_analyze_scale_factor = 0.05,
            autovacuum_vacuum_cost_delay = 5,
            fillfactor = 90
        )
    """)
    
    op.execute("""
        ALTER TABLE workflow_node_executions SET (
            autovacuum_vacuum_scale_factor = 0.05,
            autovacuum_analyze_scale_factor = 0.05,
            autovacuum_vacuum_cost_delay = 5,
            fillfactor = 85
        )
    """)
    
    # ============================================
    # 批量写入表优化（文档分块）
    # ============================================
    op.execute("""
        ALTER TABLE document_chunks SET (
            autovacuum_vacuum_scale_factor = 0.1,
            autovacuum_analyze_scale_factor = 0.05,
            autovacuum_vacuum_cost_delay = 10,
            fillfactor = 95
        )
    """)


def downgrade() -> None:
    tables = [
        'agent_traces',
        'agent_steps',
        'workflow_traces',
        'workflow_node_executions',
        'document_chunks'
    ]
    
    for table in tables:
        op.execute(f"""
            ALTER TABLE {table} RESET (
                autovacuum_vacuum_scale_factor,
                autovacuum_analyze_scale_factor,
                autovacuum_vacuum_cost_delay,
                fillfactor
            )
        """)
