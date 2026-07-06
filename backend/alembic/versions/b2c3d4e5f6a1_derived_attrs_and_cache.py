"""Add derived-attribute / computation-cache provenance columns

Adds the following nullable(-ish) columns to both node_attributes and
edge_attributes, in support of later caching work:

- is_derived (Boolean, NOT NULL, server default false)
- derived_from (String, nullable)
- computation_params (JSON, nullable)
- graph_state_hash (String, nullable)
- computed_at (DateTime(timezone=True), nullable)

These columns are unused (all default/null) until later refactor stages
populate them; this migration only establishes the schema.

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-02 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_COLUMNS = (
    ("is_derived", lambda: sa.Column(
        "is_derived", sa.Boolean(), nullable=False, server_default=sa.false()
    )),
    ("derived_from", lambda: sa.Column("derived_from", sa.String(), nullable=True)),
    ("computation_params", lambda: sa.Column(
        "computation_params", sa.JSON(), nullable=True
    )),
    ("graph_state_hash", lambda: sa.Column(
        "graph_state_hash", sa.String(), nullable=True
    )),
    ("computed_at", lambda: sa.Column(
        "computed_at", sa.DateTime(timezone=True), nullable=True
    )),
)


def _add_missing_columns(inspector, table_name: str) -> None:
    if not inspector.has_table(table_name):
        return
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    for column_name, make_column in _NEW_COLUMNS:
        if column_name not in existing:
            op.add_column(table_name, make_column())


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    _add_missing_columns(inspector, "node_attributes")
    _add_missing_columns(inspector, "edge_attributes")


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    for table_name in ("node_attributes", "edge_attributes"):
        if not inspector.has_table(table_name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table_name)}
        for column_name, _ in reversed(_NEW_COLUMNS):
            if column_name in existing:
                op.drop_column(table_name, column_name)
