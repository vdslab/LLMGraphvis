from app.core.mcp import mcp

# --- Prompts ---

@mcp.prompt("analyze-structure")
def analyze_structure_prompt(network_id: int) -> str:
    return f"""Please analyze the structural properties of network {network_id}.
Use the 'calculate_centrality' and 'calculate_community' tools to understand the graph structure.
Check the 'network://{network_id}/structure' resource first.
"""

@mcp.prompt("recommend-visualization")
def recommend_visualization_prompt(network_id: int) -> str:
    return f"""Based on the data in network {network_id}, recommend a suitable visualization.
Check the attributes using 'get_node_attributes_resource' and 'get_edge_attributes_resource'.
Consider using 'ForceAtlas2' for layout if the graph is large.
"""

@mcp.prompt("investigate-attributes")
def investigate_attributes_prompt(network_id: int) -> str:
    return f"""Investigate the node and edge attributes of network {network_id}.
Use the attribute resources to find interesting patterns or distributions.
"""

@mcp.prompt("find-important-nodes")
def find_important_nodes_prompt(network_id: int) -> str:
    return f"""Identify the most important nodes in network {network_id}.
Use 'calculate_centrality' with 'degree', 'betweenness', and 'closeness'.
Compare the top nodes for each metric.
"""
