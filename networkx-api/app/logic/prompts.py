from mcp.server.fastmcp import FastMCP

def analyze_structure_prompt(network_id: int) -> list[dict]:
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""Please analyze the structural characteristics of network {network_id}.
1. Read the network structure stats: `read_resource("network://{network_id}/structure")`
2. specific structural features using `calculate_centrality` if needed.
3. Summarize the topology (e.g., dense/sparse, centralized/decentralized)."""
            }
        }
    ]

def recommend_visualization_prompt(network_id: int) -> list[dict]:
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""I need a recommendation for visualizing network {network_id}.
1. **MANDATORY**: Check available attributes first: `read_resource("network://{network_id}/attributes/nodes")`. 
2. If distinct attributes exist (like 'country', 'type'), propose a `generate_visualization` call using them for `node_color_config` or `node_size_config`.
3. If NO interesting attributes exist, use a structural metric like 'degree' (calculate it first if needed) or just use the default blue color.
4. **Layout**: Default to 'forceatlas2' unless the user asks for a specific structure (like 'circle').
5. **Output**: providing the specific tool call arguments."""
            }
        }
    ]

def investigate_attributes_prompt(network_id: int) -> list[dict]:
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""I want to investigate the attributes of network {network_id}.
1. List all node attributes: `read_resource("network://{network_id}/attributes/nodes")`
2. If the list is empty, state that the network has no attributes.
3. If attributes exist, identify numerical vs categorical types and suggest potential visualizations (e.g. "Color by 'gender'")."""
            }
        }
    ]

def find_important_nodes_prompt(network_id: int) -> list[dict]:
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""Identify the most important nodes in network {network_id}.
1. Calculate basic centrality metrics if not present: `calculate_centrality` (degree, betweenness).
2. Retrieve top nodes: `read_resource("network://{network_id}/centrality/degree/top")`
3. Explain why these nodes are important (hubs, bridges) and suggest highlighting them using `focus_config` in `generate_visualization`."""
            }
        }
    ]
