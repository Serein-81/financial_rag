"""create user feedback tables

Revision ID: 016_create_feedback_tables
Revises: 015_create_custom_tools
Create Date: 2026-05-29

Creates the user feedback / failure case / improvement record tables backing
app.models.feedback. These were added with the model + API but never had a
migration, so queries against them failed with
``relation "user_feedback" does not exist``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "016_create_feedback_tables"
down_revision: Union[str, None] = "015_create_custom_tools"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


feedback_type_enum = postgresql.ENUM(
    "positive", "negative", "neutral",
    name="feedback_type_enum",
    create_type=False,
)
failure_type_enum = postgresql.ENUM(
    "retrieval", "generation", "hallucination", "incomplete", "irrelevant", "other",
    name="failure_type_enum",
    create_type=False,
)
failure_status_enum = postgresql.ENUM(
    "pending", "analyzing", "fixed", "ignored",
    name="failure_status_enum",
    create_type=False,
)
improvement_type_enum = postgresql.ENUM(
    "prompt", "retrieval", "chunking", "parameter", "other",
    name="improvement_type_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    feedback_type_enum.create(bind, checkfirst=True)
    failure_type_enum.create(bind, checkfirst=True)
    failure_status_enum.create(bind, checkfirst=True)
    improvement_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "user_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", sa.String(length=50), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("feedback_type", feedback_type_enum, server_default="neutral", nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("retrieval_method", sa.String(length=50), nullable=True),
        sa.Column("chunks_used", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("kb_id", sa.String(length=100), nullable=True),
        sa.Column("retrieval_time", sa.Integer(), nullable=True),
        sa.Column("generation_time", sa.Integer(), nullable=True),
        sa.Column("total_time", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_feedback_session_id", "user_feedback", ["session_id"], unique=False)
    op.create_index("ix_user_feedback_tenant_id", "user_feedback", ["tenant_id"], unique=False)

    op.create_table(
        "failure_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("feedback_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("failure_type", failure_type_enum, nullable=False),
        sa.Column("analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fix_suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", failure_status_enum, server_default="pending", nullable=False),
        sa.Column("auto_analyzed", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["feedback_id"], ["user_feedback.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_failure_cases_feedback_id", "failure_cases", ["feedback_id"], unique=False)

    op.create_table(
        "improvement_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("failure_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("improvement_type", improvement_type_enum, nullable=False),
        sa.Column("before_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ab_test_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deployed", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_rate_before", sa.Integer(), nullable=True),
        sa.Column("success_rate_after", sa.Integer(), nullable=True),
        sa.Column("user_satisfaction_before", sa.Integer(), nullable=True),
        sa.Column("user_satisfaction_after", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["failure_case_id"], ["failure_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_improvement_records_failure_case_id", "improvement_records", ["failure_case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_improvement_records_failure_case_id", table_name="improvement_records")
    op.drop_table("improvement_records")
    op.drop_index("ix_failure_cases_feedback_id", table_name="failure_cases")
    op.drop_table("failure_cases")
    op.drop_index("ix_user_feedback_tenant_id", table_name="user_feedback")
    op.drop_index("ix_user_feedback_session_id", table_name="user_feedback")
    op.drop_table("user_feedback")

    bind = op.get_bind()
    improvement_type_enum.drop(bind, checkfirst=True)
    failure_status_enum.drop(bind, checkfirst=True)
    failure_type_enum.drop(bind, checkfirst=True)
    feedback_type_enum.drop(bind, checkfirst=True)
