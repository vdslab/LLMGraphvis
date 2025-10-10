"""
Network operation tools for the MCP server.
Handles basic network creation, manipulation, and analysis.
"""

import logging
import random
from typing import Dict, Any, Optional

try:
    import networkx as nx
except ImportError:
    logger = logging.getLogger("networkx_mcp.tools.network_ops")
    logger.error("NetworkX not available")
    nx = None

try:
    from mcp.server.fastmcp import FastMCP, Context
    from mcp.server.session import ServerSession
    MCP_AVAILABLE = True
except ImportError:
    # Mock classes for development
    MCP_AVAILABLE = False

    class FastMCP:
        def tool(self):
            def decorator(func):
                return func
            return decorator

    class Context:
        pass

    class ServerSession:
        pass

from core.context import ServerContext
from core.graph_utils import graph_to_graphml_string, validate_graph

logger = logging.getLogger("networkx_mcp.tools.network_ops")


def register_network_tools(mcp: FastMCP):
    """Register network operation tools with the MCP server."""

    @mcp.tool()
    def create_random_graph(
        num_nodes: int = 20,
        edge_probability: float = 0.2,
        seed: Optional[int] = None,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Create a random graph using the Erdős–Rényi model.

        Args:
            num_nodes: Number of nodes in the graph (default: 20)
            edge_probability: Probability of edge creation between any two nodes (default: 0.2)
            seed: Random seed for reproducibility (optional)

        Returns:
            Dictionary containing the GraphML content and graph statistics
        """
        try:
            if seed is not None:
                random.seed(seed)

            # Create random graph
            G = nx.gnp_random_graph(num_nodes, edge_probability, seed=seed)

            # Ensure connectivity
            if not nx.is_connected(G) and num_nodes > 1:
                components = list(nx.connected_components(G))
                largest_component = max(components, key=len)
                for component in components:
                    if component != largest_component:
                        node_from = random.choice(list(component))
                        node_to = random.choice(list(largest_component))
                        G.add_edge(node_from, node_to)

            # Add basic node labels
            for i, node in enumerate(G.nodes()):
                G.nodes[node]['label'] = f"Node {node}"

            # Convert to GraphML
            graphml_content = graph_to_graphml_string(G)
            validation = validate_graph(G)

            logger.info(
                f"Created random graph with {num_nodes} nodes, edge_prob={edge_probability}")

            return {
                "success": True,
                "graphml_content": graphml_content,
                "graph_info": validation,
                "parameters": {
                    "num_nodes": num_nodes,
                    "edge_probability": edge_probability,
                    "seed": seed
                }
            }

        except Exception as e:
            error_msg = f"Failed to create random graph: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def create_small_world_graph(
        n: int = 20,
        k: int = 4,
        p: float = 0.3,
        seed: Optional[int] = None,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Create a Watts-Strogatz small-world graph.

        Args:
            n: Number of nodes
            k: Each node is joined with its k nearest neighbors in a ring topology
            p: The probability of rewiring each edge
            seed: Random seed for reproducibility

        Returns:
            Dictionary containing the GraphML content and graph statistics
        """
        try:
            if seed is not None:
                random.seed(seed)

            G = nx.watts_strogatz_graph(n, k, p, seed=seed)

            # Add node labels
            for node in G.nodes():
                G.nodes[node]['label'] = f"Node {node}"

            graphml_content = graph_to_graphml_string(G)
            validation = validate_graph(G)

            logger.info(f"Created small-world graph with n={n}, k={k}, p={p}")

            return {
                "success": True,
                "graphml_content": graphml_content,
                "graph_info": validation,
                "parameters": {
                    "n": n,
                    "k": k,
                    "p": p,
                    "seed": seed
                }
            }

        except Exception as e:
            error_msg = f"Failed to create small-world graph: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def create_scale_free_graph(
        n: int = 20,
        alpha: float = 0.41,
        beta: float = 0.54,
        gamma: float = 0.05,
        seed: Optional[int] = None,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Create a scale-free graph using the Holme and Kim algorithm.

        Args:
            n: Number of nodes
            alpha: Probability for adding a new node connected to an existing node
            beta: Probability for adding an edge between two existing nodes
            gamma: Probability for adding a new node connected to two existing nodes
            seed: Random seed for reproducibility

        Returns:
            Dictionary containing the GraphML content and graph statistics
        """
        try:
            if seed is not None:
                random.seed(seed)

            # Use Barabási–Albert model as it's more stable
            # Number of edges to attach from new node
            m = max(1, min(3, n // 4))
            G = nx.barabasi_albert_graph(n, m, seed=seed)

            # Add node labels
            for node in G.nodes():
                G.nodes[node]['label'] = f"Node {node}"

            graphml_content = graph_to_graphml_string(G)
            validation = validate_graph(G)

            logger.info(f"Created scale-free graph with n={n}, m={m}")

            return {
                "success": True,
                "graphml_content": graphml_content,
                "graph_info": validation,
                "parameters": {
                    "n": n,
                    "m": m,
                    "seed": seed
                }
            }

        except Exception as e:
            error_msg = f"Failed to create scale-free graph: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
