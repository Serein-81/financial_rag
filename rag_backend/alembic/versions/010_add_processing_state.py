"""Add processing state fields to documents table

Revision ID: 010_add_processing_state
Revises: 009_add_fts_indexes
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa


revision = '010_add_processing_state'
down_revision = '009_add_fts_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('processing_state', sa.String(20), server_default='pending', nullable=True))
    op.add_column('documents', sa.Column('processing_progress', sa.Integer(), server_default='0', nullable=True))
    op.add_column('documents', sa.Column('processing_message', sa.String(255), nullable=True))
    op.create_index('ix_documents_processing_state', 'documents', ['processing_state'])


def downgrade() -> None:
    op.drop_index('ix_documents_processing_state', table_name='documents')
    op.drop_column('documents', 'processing_message')
    op.drop_column('documents', 'processing_progress')
    op.drop_column('documents', 'processing_state')