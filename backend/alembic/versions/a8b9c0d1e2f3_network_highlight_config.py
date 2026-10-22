"""Persist the highlight channel of a network's view (ADR 0023).

Revision ID: a8b9c0d1e2f3
Revises: f7a1b2c3d4e5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "networks", sa.Column("last_highlight_config", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("networks", "last_highlight_config")
