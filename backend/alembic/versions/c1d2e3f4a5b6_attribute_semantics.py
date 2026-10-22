"""Attribute role and measurement.

node_attributes and edge_attributes gain `role` (why the attribute exists) and
`measurement` (how its values compare), so the agent can pick an encoding
without guessing from `data_type`. Derived rows are backfilled from their
provenance. Imported rows keep a null measurement here; networkx-api infers it
from the values the first time the attribute is listed.

Rows computed before provenance was recorded (2026-07), and layout
coordinates copied into subgraphs, carry no `derived_from`. They are
recognised by the names the computations give them and get their provenance
as well.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("node_attributes", "edge_attributes")

# derived_from prefix -> (role, measurement); mirrors attribute_semantics.py.
BACKFILL = (
    ("layout:%", "coordinate", "quantitative"),
    ("centrality:%", "metric", "quantitative"),
    ("community:%", "community", "categorical"),
)


# Names as of this revision: a later layout or algorithm writes its own
# provenance and never needs this.
LAYOUTS = (
    "arf", "bfs", "bipartite", "circular", "forceatlas2", "kamada_kawai",
    "multipartite", "planar", "random", "shell", "spectral", "spiral", "spring",
)
COMMUNITY_ALGORITHMS = ("louvain", "greedy_modularity", "label_propagation")


def _backfill_unmarked(table: str) -> None:
    """Provenance for computed rows that predate it, recognised by name."""
    unmarked = "NOT is_derived AND derived_from IS NULL AND attribute_name = :name"
    for layout in LAYOUTS:
        for axis in ("x", "y"):
            op.execute(
                sa.text(
                    f"UPDATE {table} SET is_derived = true, "
                    "derived_from = :source, role = 'coordinate', "
                    f"measurement = 'quantitative' WHERE {unmarked}"
                ).bindparams(source=f"layout:{layout}", name=f"{layout}_{axis}")
            )
    for algorithm in COMMUNITY_ALGORITHMS:
        op.execute(
            sa.text(
                f"UPDATE {table} SET is_derived = true, "
                "derived_from = :source, role = 'community', "
                f"measurement = 'categorical' WHERE {unmarked}"
            ).bindparams(
                source=f"community:{algorithm}", name=f"{algorithm}_community"
            )
        )


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "role",
                sa.String(),
                nullable=False,
                server_default="data",
                comment="data | metric | community | coordinate",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "measurement",
                sa.String(),
                nullable=True,
                comment="categorical | discrete | quantitative | identifier | text",
            ),
        )
        for pattern, role, measurement in BACKFILL:
            op.execute(
                sa.text(
                    f"UPDATE {table} SET role = :role, measurement = :measurement "
                    "WHERE is_derived AND derived_from LIKE :pattern"
                ).bindparams(role=role, measurement=measurement, pattern=pattern)
            )
        _backfill_unmarked(table)


def downgrade() -> None:
    # The provenance backfilled by _backfill_unmarked stays: it is true with or
    # without these columns.
    for table in TABLES:
        op.drop_column(table, "measurement")
        op.drop_column(table, "role")
