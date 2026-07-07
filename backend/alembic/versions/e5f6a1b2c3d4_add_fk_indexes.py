"""Add missing foreign-key indexes

Every hot query in the app filters on one of these FK columns
(messages by chat, tool executions by message, edges by endpoint node,
attribute values by attribute, subgraphs by parent, chats by user), but
none of them were indexed — PostgreSQL does not index FK columns
automatically. Guarded with inspector checks because some databases
(those repaired by the a1b2c3d4e5f6 drift migration) already have
ix_chat_messages_chat_id.

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (index_name, table, column)
INDEXES = [
    ("ix_chat_messages_chat_id", "chat_messages", "chat_id"),
    ("ix_tool_executions_message_id", "tool_executions", "message_id"),
    ("ix_chats_user_id", "chats", "user_id"),
    ("ix_networks_parent_network_id", "networks", "parent_network_id"),
    ("ix_edges_source_node_id", "edges", "source_node_id"),
    ("ix_edges_target_node_id", "edges", "target_node_id"),
    ("ix_node_attribute_values_attribute_id", "node_attribute_values", "attribute_id"),
    ("ix_edge_attribute_values_attribute_id", "edge_attribute_values", "attribute_id"),
]


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    for index_name, table, column in INDEXES:
        existing = {ix["name"] for ix in inspector.get_indexes(table)}
        if index_name not in existing:
            op.create_index(index_name, table, [column], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    for index_name, table, _column in INDEXES:
        existing = {ix["name"] for ix in inspector.get_indexes(table)}
        if index_name in existing:
            op.drop_index(index_name, table_name=table)
