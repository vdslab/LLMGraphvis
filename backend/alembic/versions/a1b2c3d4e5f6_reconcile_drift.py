"""Reconcile schema drift from manual patch scripts

This migration idempotently reconciles schema drift that was historically
introduced by ad-hoc, out-of-band patch scripts that used to run directly
against Postgres instead of through Alembic:

- networkx-api/add_parent_network_column.py
- scripts/repair_chat_messages_schema.py
- scripts/update_chat_schema.py
- scripts/inspect_and_repair_chat_messages.py

Those scripts are removed as part of this change; this migration supersedes
them so that any of the following starting states converge to the same,
correct schema:
  (a) a brand-new empty database
  (b) a database that already had every manual patch applied
  (c) a database with only the initial Alembic migration applied

Every individual change below is guarded by an inspector-based existence
check so this migration is safe to run against any of the above states.

Revision ID: a1b2c3d4e5f6
Revises: 720787691d58
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '720787691d58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ------------------------------------------------------------------
    # networks.parent_network_id
    # (superseded: networkx-api/add_parent_network_column.py)
    # ------------------------------------------------------------------
    if inspector.has_table("networks"):
        network_columns = {c["name"] for c in inspector.get_columns("networks")}
        if "parent_network_id" not in network_columns:
            op.add_column(
                "networks",
                sa.Column("parent_network_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_networks_parent_network_id",
                "networks",
                "networks",
                ["parent_network_id"],
                ["id"],
            )

    # ------------------------------------------------------------------
    # chats.visualization_state
    # (superseded: scripts/update_chat_schema.py)
    # ------------------------------------------------------------------
    if inspector.has_table("chats"):
        chat_columns = {c["name"] for c in inspector.get_columns("chats")}
        if "visualization_state" not in chat_columns:
            op.add_column(
                "chats",
                sa.Column("visualization_state", sa.JSON(), nullable=True),
            )

    # ------------------------------------------------------------------
    # chat_messages table / columns
    # (superseded: scripts/repair_chat_messages_schema.py,
    #              scripts/inspect_and_repair_chat_messages.py)
    # ------------------------------------------------------------------
    # Re-inspect: an earlier op in this function may have changed table state.
    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("chat_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("meta_data", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["chat_id"], ["chats.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False
        )
    else:
        chat_message_columns = {
            c["name"] for c in inspector.get_columns("chat_messages")
        }
        existing_indexes = {
            ix["name"] for ix in inspector.get_indexes("chat_messages")
        }
        if "chat_id" not in chat_message_columns:
            # Legacy drifted tables may already contain rows, so the column
            # is added nullable here (mirrors the original patch script's
            # behavior) rather than failing on a NOT NULL backfill.
            op.add_column(
                "chat_messages", sa.Column("chat_id", sa.Integer(), nullable=True)
            )
            if "ix_chat_messages_chat_id" not in existing_indexes:
                op.create_index(
                    "ix_chat_messages_chat_id",
                    "chat_messages",
                    ["chat_id"],
                    unique=False,
                )
            op.create_foreign_key(
                "fk_chat_messages_chat_id",
                "chat_messages",
                "chats",
                ["chat_id"],
                ["id"],
            )
        if "meta_data" not in chat_message_columns:
            op.add_column(
                "chat_messages", sa.Column("meta_data", sa.JSON(), nullable=True)
            )
        if "updated_at" not in chat_message_columns:
            op.add_column(
                "chat_messages",
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("now()"),
                    nullable=True,
                ),
            )
        if op.f("ix_chat_messages_id") not in existing_indexes:
            op.create_index(
                op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False
            )

    # ------------------------------------------------------------------
    # tool_executions table
    # This table was never captured by the initial Alembic migration; it
    # historically only ever got created via ad-hoc Base.metadata.create_all()
    # calls in application startup code. Create it here if missing so a
    # database bootstrapped purely from Alembic still gets it.
    # ------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if not inspector.has_table("tool_executions"):
        op.create_table(
            "tool_executions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("message_id", sa.Integer(), nullable=False),
            sa.Column("tool_name", sa.String(), nullable=False),
            sa.Column("arguments", sa.JSON(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("thought", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_tool_executions_id"), "tool_executions", ["id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema.

    Note: this reconciliation migration is intentionally not fully
    reversible for the drift-repair branches (we don't want to drop columns
    that pre-existing, non-Alembic-managed databases may have already
    depended on). The tables/columns that this migration is solely
    responsible for introducing are removed below on a best-effort basis.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("tool_executions"):
        op.drop_index(op.f("ix_tool_executions_id"), table_name="tool_executions")
        op.drop_table("tool_executions")
