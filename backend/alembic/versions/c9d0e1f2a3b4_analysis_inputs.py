"""Persist conversational input requests independently of SSE connections."""

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_inputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "chat_id",
            sa.Integer(),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "network_id",
            sa.Integer(),
            sa.ForeignKey("networks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("specification", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_analysis_inputs_chat_id", "analysis_inputs", ["chat_id"])


def downgrade():
    op.drop_table("analysis_inputs")
