from typing import Annotated, Optional
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def analysis_degree_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    normalized: Annotated[bool, Field(description="If True (default), scores are the fraction of other nodes each node is connected to (degree / (n-1)). If False, returns raw degree counts instead.")] = True,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates degree centrality for all nodes and saves as 'degree_centrality' attribute.

    Degree centrality = fraction of other nodes each node is connected to.
    Simple but effective: high-degree nodes are direct hubs.
    Saved attribute name: 'degree_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(
            network_id, "degree", db, normalized=normalized, force=force_recompute
        )
        return "Degree centrality calculated and saved as 'degree_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_betweenness_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    weight: Annotated[Optional[str], Field(description="Name of an edge attribute to use as edge weight/distance when computing shortest paths ('weight' reads the imported weight; other names read numeric edge attributes). Defaults to unweighted (all edges treated as distance 1) if not specified.")] = None,
    normalized: Annotated[bool, Field(description="If True (default), scores are normalized by the number of node pairs. If False, returns raw (unnormalized) betweenness counts.")] = True,
    k: Annotated[Optional[int], Field(description="If set, uses approximate betweenness via sampling k source nodes instead of computing exactly over all nodes — trades accuracy for speed on large graphs (addresses the O(N*E) cost warned about below). Defaults to exact computation (all nodes) if not specified.")] = None,
    seed: Annotated[Optional[int], Field(description="Seed for sampled sources when k is set. Defaults to 42 for reproducibility; null uses NetworkX randomness.")] = 42,
    endpoints: Annotated[bool, Field(description="Include the source and target endpoints in betweenness counts.")] = False,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates betweenness centrality for all nodes and saves as 'betweenness_centrality' attribute.

    Betweenness centrality measures how often a node lies on the shortest path between other nodes.
    High values = bridge/broker nodes controlling information flow.
    WARNING: O(N * E) complexity — can be slow on very large graphs. Consider setting `k`
    to sample an approximate result on large networks.
    Saved attribute name: 'betweenness_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(
            network_id,
            "betweenness",
            db,
            weight=weight,
            normalized=normalized,
            k=k,
            seed=seed,
            endpoints=endpoints,
            force=force_recompute,
        )
        return "Betweenness centrality calculated and saved as 'betweenness_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_closeness_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    weight: Annotated[Optional[str], Field(description="Name of an edge attribute to use as edge weight/distance when computing shortest paths ('weight' reads the imported weight; other names read numeric edge attributes). Defaults to unweighted (all edges treated as distance 1) if not specified.")] = None,
    wf_improved: Annotated[bool, Field(description="Scale by the fraction of nodes that can reach each node (Wasserman-Faust correction). Useful for disconnected graphs; defaults to True.")] = True,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates closeness centrality for all nodes and saves as 'closeness_centrality' attribute.

    Closeness centrality = inverse of average shortest-path distance to all other nodes.
    For directed graphs, NetworkX uses incoming distances: high values indicate nodes reached quickly by others. This does not measure outgoing reach.
    Saved attribute name: 'closeness_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(
            network_id, "closeness", db, weight=weight, wf_improved=wf_improved, force=force_recompute
        )
        return "Closeness centrality calculated and saved as 'closeness_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_eigenvector_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    weight: Annotated[Optional[str], Field(description="Name of an edge attribute to use as edge weight ('weight' reads the imported weight; other names read numeric edge attributes). Defaults to unweighted if not specified.")] = None,
    max_iter: Annotated[Optional[int], Field(description="Maximum power-iteration steps before giving up on convergence. Defaults to 1000 if not specified.")] = None,
    tol: Annotated[Optional[float], Field(description="Convergence tolerance (error tolerance used to check convergence). Defaults to networkx's own default (1e-06) if not specified.")] = None,
    nstart: Annotated[Optional[dict[str, float]], Field(description="Initial eigenvector keyed by exact node ID; should cover the graph and have a nonzero sum. Omit for the all-ones vector.")] = None,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates eigenvector centrality for all nodes and saves as 'eigenvector_centrality' attribute.

    Eigenvector centrality rewards being connected to other high-centrality nodes.
    Supports directed graphs using incoming edges. Useful for finding influential nodes in dense networks.
    Saved attribute name: 'eigenvector_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(
            network_id,
            "eigenvector",
            db,
            weight=weight,
            max_iter=max_iter,
            tol=tol,
            nstart=nstart,
            force=force_recompute,
        )
        return "Eigenvector centrality calculated and saved as 'eigenvector_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_pagerank(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    damping_factor: Annotated[float, Field(description="Damping factor (alpha) for PageRank. Default 0.85.")] = 0.85,
    weight: Annotated[Optional[str], Field(description="Numeric edge strength attribute; 'weight' uses imported weights. Omit or pass null/'none' for unweighted PageRank, preserving the app's earlier behavior.")] = None,
    personalization: Annotated[Optional[dict[str, float]], Field(description="Teleportation distribution by exact node ID; unspecified nodes receive zero. Values must have nonzero sum. Omit for uniform teleportation.")] = None,
    dangling: Annotated[Optional[dict[str, float]], Field(description="Distribution for nodes with no outgoing edges. Omit to use personalization (uniform when that is omitted). Must define an irreducible transition matrix with the graph.")] = None,
    nstart: Annotated[Optional[dict[str, float]], Field(description="Initial rank distribution keyed by node ID. Omit for uniform initialization.")] = None,
    max_iter: Annotated[int, Field(gt=0, description="Maximum power iterations before a convergence error. Defaults to 100.")] = 100,
    tol: Annotated[float, Field(gt=0, allow_inf_nan=False, description="Convergence tolerance; iteration ends when error is less than node_count times tol.")] = 1e-6,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates PageRank for all nodes and saves as 'pagerank' attribute.

    PageRank scores nodes by the quality and quantity of links pointing to them
    (originally developed by Google). High PageRank = important node in the network.
    Saved attribute name: 'pagerank'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(
            network_id,
            "pagerank",
            db,
            damping_factor=damping_factor,
            weight=weight, personalization=personalization, dangling=dangling,
            nstart=nstart, max_iter=max_iter, tol=tol,
            force=force_recompute,
        )
        return "PageRank calculated and saved as 'pagerank'."


@mcp.tool()
@handle_tool_errors
def analysis_clustering_coefficient(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates the local clustering coefficient for each node and saves as 'clustering' attribute.

    The clustering coefficient measures the fraction of a node's neighbors that are
    also connected to each other (i.e., how clique-like the local neighborhood is).
    Values range from 0 (no triangles) to 1 (all neighbors are fully connected).
    Saved attribute name: 'clustering'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic.attributes import (
            bulk_save_node_attributes,
            get_cached_attribute,
            is_cache_valid,
            load_node_attribute_values,
            update_attribute_cache_metadata,
        )
        from app.logic.utils.cache import compute_graph_state_hash
        from common import models

        attr_name = "clustering"
        current_hash = compute_graph_state_hash(network_id, db)
        effective_params = {}

        if not force_recompute:
            cached = get_cached_attribute(network_id, attr_name, models.NodeAttribute, db)
            if is_cache_valid(cached, current_hash, effective_params):
                values = load_node_attribute_values(network_id, attr_name, db)
                avg = sum(values.values()) / len(values) if values else 0
                return (
                    f"Clustering coefficients (cached) for 'clustering'. Average: {avg:.4f}"
                )

        import networkx as nx
        from app.logic.utils.graph_builder import build_graph_from_db

        G = build_graph_from_db(network_id, db)
        clustering = nx.clustering(G)

        nodes = db.query(models.Node.id, models.Node.node_id).filter(
            models.Node.network_id == network_id
        ).all()
        node_map = {n.node_id: n.id for n in nodes}

        data_map = {
            node_map[nid]: val
            for nid, val in clustering.items()
            if nid in node_map
        }

        bulk_save_node_attributes(network_id, attr_name, "float", data_map, db)
        update_attribute_cache_metadata(
            network_id,
            attr_name,
            models.NodeAttribute,
            db,
            graph_state_hash=current_hash,
            computation_params=effective_params,
            is_derived=True,
            derived_from="centrality:clustering",
        )
        avg = sum(clustering.values()) / len(clustering) if clustering else 0
        return f"Clustering coefficients calculated and saved as 'clustering'. Average: {avg:.4f}"


@mcp.tool()
@handle_tool_errors
def analysis_in_degree_centrality(
    network_id: Annotated[int, Field(description="ID of a directed network.")],
    normalized: Annotated[bool, Field(description="Divide incoming degree by n-1 when True; otherwise store raw incoming degree.")] = True,
    force_recompute: bool = False,
) -> str:
    """Save incoming-degree centrality as 'in_degree_centrality'; no rendering.

    Requires a directed graph. Measures received connections, not outgoing reach.
    """
    with get_db_context() as db:
        from app.logic.centrality import calculate_centrality
        calculate_centrality(network_id, "in_degree", db, normalized=normalized, force=force_recompute)
        return "Saved 'in_degree_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_out_degree_centrality(
    network_id: Annotated[int, Field(description="ID of a directed network.")],
    normalized: Annotated[bool, Field(description="Divide outgoing degree by n-1 when True; otherwise store raw outgoing degree.")] = True,
    force_recompute: bool = False,
) -> str:
    """Save outgoing-degree centrality as 'out_degree_centrality'; no rendering.

    Requires a directed graph. Measures sent connections, not incoming influence.
    """
    with get_db_context() as db:
        from app.logic.centrality import calculate_centrality
        calculate_centrality(network_id, "out_degree", db, normalized=normalized, force=force_recompute)
        return "Saved 'out_degree_centrality'."
