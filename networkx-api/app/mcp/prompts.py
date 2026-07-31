from app.core.mcp import mcp

# --- Prompts ---
# Each prompt describes a reusable analysis workflow. Only reference tool names
# that actually exist under app/mcp/tools/ (network_*, node_*, subgraph_*,
# analysis_*, layout_*, visualization_*) and resources under the network://
# scheme (see app/mcp/resources.py).


@mcp.prompt("analyze-structure")
def analyze_structure_prompt(network_id: int) -> str:
    """Analyze the overall structural properties of a network."""
    return f"""Please analyze the structural properties of network {network_id}.

1. Read the `network://{network_id}/structure` resource first to get node/edge counts, density, and whether the graph is directed.
2. Run `analysis_detect_communities` to reveal how the graph partitions into groups, and `analysis_clustering_coefficient` to measure how tightly nodes cluster.
3. Compute centrality with `analysis_degree_centrality` (and `analysis_betweenness_centrality` if bridging structure matters) to identify hubs.
4. Summarize the structure: size, density, community count, and any notable hubs or bridges.
"""


@mcp.prompt("recommend-visualization")
def recommend_visualization_prompt(network_id: int) -> str:
    """Recommend and apply a suitable visualization for a network."""
    return f"""Based on the data in network {network_id}, recommend a suitable visualization.

1. Inspect the available data with `network_list_node_attributes` and `network_list_edge_attributes` (or the `network://{network_id}/attributes/nodes` resource).
2. Choose a layout: `layout_forceatlas2` is a good default for revealing structure, especially on larger graphs; consider `layout_circular` or `layout_kamada_kawai` for small or highly structured graphs. Render it with `visualization_generate`.
3. Propose meaningful encodings — e.g. color by a categorical attribute with `visualization_set_node_color`, size by a centrality attribute with `visualization_set_node_size` — and explain the reasoning before applying.
"""


@mcp.prompt("investigate-attributes")
def investigate_attributes_prompt(network_id: int) -> str:
    """Investigate node and edge attributes to find interesting patterns."""
    return f"""Investigate the node and edge attributes of network {network_id}.

1. List what exists with `network_list_node_attributes` and `network_list_edge_attributes`.
2. For an interesting attribute, read its distribution via the `network://{network_id}/attributes/nodes/{{attribute_name}}` resource (or the edges equivalent).
3. Drill into subsets with `node_filter` to see how attribute values relate to structure.
4. Report notable distributions, correlations, or outliers you find.
"""


@mcp.prompt("find-important-nodes")
def find_important_nodes_prompt(network_id: int) -> str:
    """Identify and compare the most important nodes by several centrality metrics."""
    return f"""Identify the most important nodes in network {network_id}.

1. Compute `analysis_degree_centrality`, `analysis_betweenness_centrality`, and `analysis_closeness_centrality`.
2. Use `node_get_top_ranked` on each resulting attribute ('degree_centrality', 'betweenness_centrality', 'closeness_centrality') to get the top nodes per metric.
3. Compare the rankings: nodes that top multiple metrics are robustly central, while a node high only in betweenness is likely a bridge.
4. Report the standout nodes and what each metric says about their role.
"""


@mcp.prompt("explore-subgraphs")
def explore_subgraphs_prompt(network_id: int) -> str:
    """Extract and explore meaningful subgraphs of a network."""
    return f"""Explore meaningful subgraphs of network {network_id}.

1. Check what already exists with `subgraph_list` (or the `network://{network_id}/subgraphs` resource).
2. Extract subgraphs that match the analysis intent:
   - `analysis_detect_communities` then `subgraph_community` to isolate one detected community.
   - `subgraph_ego_network` to focus on the neighborhood around a specific node.
   - `subgraph_k_core` to peel away the periphery and expose the dense core.
   - `subgraph_largest_component` to drop disconnected noise.
3. Switch the active view to a subgraph with `visualization_switch_network` so it is actually displayed.
4. Report what each subgraph reveals.
"""


@mcp.prompt("highlight-communities")
def highlight_communities_prompt(network_id: int) -> str:
    """Detect communities and visualize them by color and size."""
    return f"""Reveal and visualize the community structure of network {network_id}.

1. Run `analysis_detect_communities` and read its returned status message for the exact saved attribute name (e.g. 'louvain_community').
2. Color nodes by that exact attribute using `visualization_set_node_color` with `scale_type='CATEGORICAL'`, then report the community-to-color mapping from the returned legend.
3. Optionally emphasize hubs: compute `analysis_degree_centrality` and size nodes by 'degree_centrality' with `visualization_set_node_size`.
4. Summarize how many communities were found and how they are distributed.
"""
