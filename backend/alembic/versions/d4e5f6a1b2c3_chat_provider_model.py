"""Add provider/model columns to chats

Lets each chat pin a specific LLM provider + model, overriding the
process-wide LLM_PROVIDER/GEMINI_MODEL/CLAUDE_MODEL env vars for that chat's
turns. NULL means "use the server default", so existing chats keep working
unchanged.

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    chat_columns = {c["name"] for c in inspector.get_columns("chats")}

    if "provider" not in chat_columns:
        op.add_column("chats", sa.Column("provider", sa.String(), nullable=True))
    if "model" not in chat_columns:
        op.add_column("chats", sa.Column("model", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    chat_columns = {c["name"] for c in inspector.get_columns("chats")}

    if "model" in chat_columns:
        op.drop_column("chats", "model")
    if "provider" in chat_columns:
        op.drop_column("chats", "provider")
