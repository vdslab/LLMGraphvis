"""Detailed LLM usage and per-user settings.

llm_usages gains the normalized cache-write and reasoning counts, a per-call
breakdown, and chat/user attribution so rows without a message (title
generation, turns that stored nothing) still count (ADR 0025). users gains
a token_version for sign-out-everywhere on password change and a default
provider/model (ADR 0026).

Revision ID: b0c1d2e3f4a5
Revises: a8b9c0d1e2f3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("default_provider", sa.String(), nullable=True))
    op.add_column("users", sa.Column("default_model", sa.String(), nullable=True))

    op.alter_column(
        "llm_usages", "message_id", existing_type=sa.Integer(), nullable=True
    )
    op.add_column("llm_usages", sa.Column("chat_id", sa.Integer(), nullable=True))
    op.add_column("llm_usages", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column(
        "llm_usages",
        sa.Column("purpose", sa.String(), nullable=False, server_default="agent_turn"),
    )
    op.add_column(
        "llm_usages",
        sa.Column(
            "cache_write_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "llm_usages",
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("llm_usages", sa.Column("calls", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_llm_usages_chat_id",
        "llm_usages",
        "chats",
        ["chat_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_usages_user_id",
        "llm_usages",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_llm_usages_chat_id", "llm_usages", ["chat_id"])
    op.create_index("ix_llm_usages_user_id", "llm_usages", ["user_id"])
    op.create_index("ix_llm_usages_created_at", "llm_usages", ["created_at"])

    # Attribute existing rows through their message. Their counts keep the
    # old, provider-specific meaning; they cannot be recomputed.
    op.execute(
        """
        UPDATE llm_usages AS u
        SET chat_id = c.id, user_id = c.user_id
        FROM chat_messages AS m JOIN chats AS c ON c.id = m.chat_id
        WHERE u.message_id = m.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usages_created_at", table_name="llm_usages")
    op.drop_index("ix_llm_usages_user_id", table_name="llm_usages")
    op.drop_index("ix_llm_usages_chat_id", table_name="llm_usages")
    op.drop_constraint("fk_llm_usages_user_id", "llm_usages", type_="foreignkey")
    op.drop_constraint("fk_llm_usages_chat_id", "llm_usages", type_="foreignkey")
    for column in (
        "calls",
        "reasoning_tokens",
        "cache_write_tokens",
        "purpose",
        "user_id",
        "chat_id",
    ):
        op.drop_column("llm_usages", column)
    op.execute("DELETE FROM llm_usages WHERE message_id IS NULL")
    op.alter_column(
        "llm_usages", "message_id", existing_type=sa.Integer(), nullable=False
    )

    op.drop_column("users", "default_model")
    op.drop_column("users", "default_provider")
    op.drop_column("users", "token_version")
