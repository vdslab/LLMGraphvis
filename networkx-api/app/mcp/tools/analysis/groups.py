"""Attribute-level questions answered as distributions, not node lists."""

from typing import Annotated, Optional

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp
from app.logic import exploration
from pydantic import Field

NetworkId = Annotated[int, Field(description="ID of the network to query.")]


@mcp.tool()
@handle_tool_errors
def analysis_attribute_distribution(
    network_id: NetworkId,
    attribute: Annotated[str, Field(description="Node attribute to describe, imported or computed (e.g. 'pagerank', 'country').")],
    group_by: Annotated[Optional[str], Field(description="Optional second node attribute (usually categorical, e.g. a community) to break the description down by group.")] = None,
    bins: Annotated[int, Field(ge=2, le=30, description="Histogram bins for a numeric attribute.")] = 10,
    top: Annotated[int, Field(ge=1, le=50, description="Most frequent categories, or largest groups, to list; the rest are counted, not listed.")] = 15,
) -> dict:
    """Describe how one node attribute is distributed, optionally per group.

    Numeric attributes get min/max/mean/median and a histogram; categorical
    ones get value counts. With group_by, each group gets its own summary
    (e.g. mean pagerank per community). Use this instead of reading many
    nodes to answer "how is X spread", "which group has the highest X", or to
    choose a color scale. Read-only.
    """
    with get_db_context() as db:
        return exploration.attribute_distribution(
            network_id, db, attribute, group_by, bins, top
        )


@mcp.tool()
@handle_tool_errors
def analysis_group_connectivity(
    network_id: NetworkId,
    attribute: Annotated[str, Field(description="Categorical node attribute that defines the groups, e.g. 'louvain_community' or 'country'.")],
    top: Annotated[int, Field(ge=1, le=50, description="Largest groups and strongest group pairs to list.")] = 20,
) -> dict:
    """Count edges within each group and between pairs of groups.

    Answers "which communities are connected to each other", "how separated
    are the groups" (`within_share`: share of edges that stay inside a group)
    and which group pairs are most linked. Undirected graphs count a pair once.
    Read-only; pair it with visualization_set_node_color on the same attribute
    to show the groups.
    """
    with get_db_context() as db:
        return exploration.group_connectivity(network_id, db, attribute, top)
