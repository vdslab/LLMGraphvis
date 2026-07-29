from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def subgraph_ego_network(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    center_node_id: Annotated[str, Field(description="The string ID of the center node.")],
    radius: Annotated[int, Field(description="Hop radius: 1 = direct neighbors only, 2 = neighbors-of-neighbors, etc.")] = 1
) -> dict:
    """
    Creates an ego network — a subgraph centered on one node including all neighbors within a given radius.

    Ego networks are useful for exploring the local context of an important node
    (e.g., "show me everyone connected to node X within 2 hops").
    Use `node_search` first to find the center node ID.
    After creation, call `visualization_switch_network(new_network_id)` to display.

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        result = subgraph.create_ego_network(
            source_network_id=network_id,
            center_node_id=center_node_id,
            radius=radius,
            db=db,
            preserve_layout=True,
            description=f"Ego network of '{center_node_id}' (radius={radius})."
        )
        new_id = result["new_network_id"]
        vis_data = visualization_builder.build_visualization(db, new_id)
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Ego network created (ID: {new_id}) centered on '{center_node_id}' (radius={radius})."
        }


@mcp.tool()
@handle_tool_errors
def subgraph_community(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    community_id: Annotated[str, Field(description="The community label to extract (as assigned by analysis_detect_communities).")],
    community_attribute: Annotated[str, Field(description="The exact node attribute name holding community labels. Pass the exact attribute name returned by `analysis_detect_communities` (e.g. 'louvain_community').")]
) -> dict:
    """
    Creates a subgraph containing only nodes belonging to a specific community.

    Run `analysis_detect_communities` first, then use this to isolate one community for
    deeper analysis. The community_attribute MUST match the exact attribute name reported
    by `analysis_detect_communities` (e.g. 'louvain_community', 'greedy_modularity_community') —
    it is NOT a fixed attribute called 'community'. The community_id corresponds to values
    of that attribute.
    After creation, call `visualization_switch_network(new_network_id)` to display.

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import visualization_builder, filter as filter_logic
        from app.schemas.filter import AttributeCondition

        condition = AttributeCondition(
            attribute_name=community_attribute,
            categories=[community_id]
        )
        result = filter_logic.create_subgraph_by_filter(
            network_id=network_id,
            conditions=[condition],
            suffix="_community",
            db=db,
            preserve_layout=True,
            description=f"Community '{community_id}' subgraph (attribute='{community_attribute}')."
        )
        new_id = result["new_network_id"]
        vis_data = visualization_builder.build_visualization(db, new_id)
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Community subgraph created (ID: {new_id}) for community '{community_id}'."
        }


@mcp.tool()
@handle_tool_errors
def subgraph_k_core(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    k: Annotated[int, Field(description="Core number k: the largest subgraph where every node has degree >= k.")],
    preserve_layout: Annotated[bool, Field(description="If True, copies x,y coordinates from the source network.")] = True
) -> dict:
    """
    Creates a k-core subgraph — the densest cohesive subgroup in the network.

    The k-core is the largest subgraph where every node has at least k connections to other nodes
    in the subgraph. Higher k = more tightly connected core. Useful for finding the most
    interconnected part of a network (e.g., the "inner circle" of a social network).
    After creation, call `visualization_switch_network(new_network_id)` to display.

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        result = subgraph.create_k_core_subgraph(
            source_network_id=network_id,
            k=k,
            db=db,
            preserve_layout=preserve_layout
        )
        vis_data = visualization_builder.build_visualization(db, result["new_network_id"])
        return {
            "network_id": result["new_network_id"],
            "network": vis_data,
            "content": f"K-core subgraph created (ID: {result['new_network_id']}, k={k})."
        }


@mcp.tool()
@handle_tool_errors
def subgraph_largest_component(
    network_id: Annotated[int, Field(description="The ID of the source network.")]
) -> dict:
    """
    Creates a subgraph containing only the largest connected component.

    Many real-world networks have isolated nodes or small disconnected islands.
    This tool filters them out, keeping only the main connected portion for analysis.
    Useful as a preprocessing step before running algorithms that require connectivity.
    After creation, call `visualization_switch_network(new_network_id)` to display.

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        result = subgraph.create_largest_component_subgraph(
            source_network_id=network_id,
            db=db,
            preserve_layout=True,
            description="Largest connected component of the network."
        )
        new_id = result["new_network_id"]
        vis_data = visualization_builder.build_visualization(db, new_id)
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Largest component subgraph created (ID: {new_id})."
        }


@mcp.tool()
@handle_tool_errors
def subgraph_high_degree_nodes(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    min_degree: Annotated[int, Field(description="Minimum degree threshold. Only nodes with degree >= this value are kept.")]
) -> dict:
    """
    Creates a subgraph containing only nodes with degree at or above a threshold.

    Useful for focusing on the most connected/active nodes in a network
    (e.g., "show only nodes with at least 5 connections"). Removes peripheral,
    low-degree nodes to reveal the backbone of the network.
    After creation, call `visualization_switch_network(new_network_id)` to display.

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        result = subgraph.filter_nodes_by_degree(
            source_network_id=network_id,
            min_degree=min_degree,
            db=db,
            preserve_layout=True,
            description=f"Nodes with degree >= {min_degree}."
        )
        new_id = result["new_network_id"]
        vis_data = visualization_builder.build_visualization(db, new_id)
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"High-degree subgraph created (ID: {new_id}, min_degree={min_degree})."
        }
