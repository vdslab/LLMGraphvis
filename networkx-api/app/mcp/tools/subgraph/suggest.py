from typing import Annotated, Optional

from pydantic import Field

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp


@mcp.tool()
@handle_tool_errors
def subgraph_suggest_reduction(
    network_id: Annotated[int, Field(description="The ID of the network to shrink.")],
    target_nodes: Annotated[
        Optional[int],
        Field(
            ge=2,
            description="Roughly how many nodes the reduced network should keep. Omit to use the default, a size that lays out comfortably. It only chooses the k-core level and the degree cut-off; the other candidates have a fixed size.",
        ),
    ] = None,
) -> dict:
    """Measure ways to shrink a large network, without creating anything.

    Read-only. For each candidate it reports the node and edge counts that would
    remain, what is dropped and what is kept, and the existing tool and
    arguments that would apply it: the largest connected part
    (`subgraph_largest_component`), a k-core (`subgraph_k_core`, with the sizes
    of the other k levels), the most connected nodes
    (`subgraph_high_degree_nodes`), and, for categorical attributes with only a
    few values, the size of each group (`subgraph_extract_filter`; replace
    `<value>` with the chosen values), and, for a dense network, edge
    backbones that keep every node but only its k strongest edges
    (`subgraph_edge_backbone`, with the edges and connected parts each k
    leaves; the remedy for a hairball). A candidate is omitted when it does not
    apply, e.g. the network is already connected.

    `large` says whether the network is above the size at which the default
    layout has to cut its iterations short (`large_threshold_nodes`).

    Present the candidates to the user and let them choose; reducing changes
    what every later analysis is computed on. Applying one is a call to the
    named tool.

    Returns:
        dict: {"nodes", "edges", "large", "large_threshold_nodes",
        "target_nodes", "candidates": [...], "attributes_omitted", "content"}
    """
    with get_db_context() as db:
        from app.logic import reduction

        result = reduction.suggest_reductions(network_id, db, target_nodes)
        sizes = ", ".join(
            f"{c['method']} -> {c['nodes']} nodes"
            for c in result["candidates"]
            if "nodes" in c
        )
        result["content"] = (
            f"Network {network_id} has {result['nodes']} nodes and "
            f"{result['edges']} edges"
            f"{' (large)' if result['large'] else ''}. "
            f"{len(result['candidates'])} reduction candidates"
            f"{': ' + sizes if sizes else ''}. Nothing was created."
        )
        return result
