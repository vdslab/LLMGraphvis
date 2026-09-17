"""Persist parameter tuning sessions shared by the agent and the panel.

Revision ID: a2b3c4d5e6f7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parameter_tunings",
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
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("initial_values", sa.JSON(), nullable=False),
        sa.Column("suggested_values", sa.JSON(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("last_result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("activated_tools", sa.JSON(), nullable=True),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_parameter_tunings_chat_id", "parameter_tunings", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_parameter_tunings_chat_id", table_name="parameter_tunings")
    op.drop_table("parameter_tunings")
