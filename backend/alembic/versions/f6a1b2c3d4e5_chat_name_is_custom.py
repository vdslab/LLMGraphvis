"""Add name_is_custom flag to chats

Marks a chat whose name the user set by hand. Auto-naming (the uploaded
filename, then the LLM-generated title) skips those chats forever, so a manual
rename is never overwritten. Existing chats default to false, i.e. they stay
eligible for auto-naming.

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e5f6a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    chat_columns = {c["name"] for c in inspector.get_columns("chats")}

    if "name_is_custom" not in chat_columns:
        op.add_column(
            "chats",
            sa.Column(
                "name_is_custom",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    chat_columns = {c["name"] for c in inspector.get_columns("chats")}

    if "name_is_custom" in chat_columns:
        op.drop_column("chats", "name_is_custom")
