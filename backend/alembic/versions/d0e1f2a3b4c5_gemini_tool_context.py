"""Persist provider tool-call context required by Gemini 3.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable fields so existing tool executions remain valid."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("tool_executions")}
    if "call_id" not in columns:
        op.add_column(
            "tool_executions",
            sa.Column("call_id", sa.String(), nullable=True),
        )
    if "thought_signature" not in columns:
        op.add_column(
            "tool_executions",
            sa.Column("thought_signature", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Remove Gemini tool-call context fields."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("tool_executions")}
    if "thought_signature" in columns:
        op.drop_column("tool_executions", "thought_signature")
    if "call_id" in columns:
        op.drop_column("tool_executions", "call_id")
