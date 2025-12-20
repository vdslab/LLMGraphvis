import networkx as nx


def resolve_node_id(G: nx.Graph, node_id_input: str) -> str:
    """
    Tries to resolve the node_id_input to a node in G.
    Handles cases where LLM adds 'Node ' prefix or similar.
    """
    if node_id_input in G:
        return node_id_input

    # Try stripping "node " or "Node " (case insensitive)
    lower_input = node_id_input.lower()
    if lower_input.startswith("node"):
        # Remove "node" and any following whitespace
        cleaned = lower_input.replace("node", "").strip()
        if cleaned in G:
            return cleaned

    # Try stripping whitespace
    stripped = node_id_input.strip()
    if stripped in G:
        return stripped

    return node_id_input
