"""Carry the turn's exposed tool set across an ask_user answer.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-13 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a nullable column; questions asked before this stay valid (NULL)."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("analysis_inputs")}
    if "activated_tools" not in columns:
        op.add_column(
            "analysis_inputs",
            sa.Column("activated_tools", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("analysis_inputs")}
    if "activated_tools" in columns:
        op.drop_column("analysis_inputs", "activated_tools")
