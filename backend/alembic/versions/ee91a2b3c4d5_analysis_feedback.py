"""Store clarity feedback for an assistant analysis operation.

Revision ID: ee91a2b3c4d5
Revises: a2b3c4d5e6f7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ee91a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "chat_id",
            sa.Integer(),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("clarity", sa.String(), nullable=False),
        sa.Column("area", sa.String(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_feedback_chat_id", "analysis_feedback", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_feedback_chat_id", table_name="analysis_feedback")
    op.drop_table("analysis_feedback")
