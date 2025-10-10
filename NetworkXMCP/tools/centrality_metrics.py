"""
Centrality metrics calculation tools for the MCP server.
Handles various centrality measures and network analysis metrics.
"""

import logging
from typing import Dict, Any, Optional
import networkx as nx
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from core.context import ServerContext
from core.graph_utils import parse_graphml_content

logger = logging.getLogger("networkx_mcp.tools.centrality")


def register_centrality_tools(mcp: FastMCP):
    """Register centrality calculation tools with the MCP server."""

    @mcp.tool()
    def calculate_degree_centrality(
        graphml_content: str,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Calculate degree centrality for all nodes in the graph.

        Args:
            graphml_content: GraphML content as string

        Returns:
            Dictionary containing centrality values for each node
        """
        try:
            G = parse_graphml_content(graphml_content)
            centrality = nx.degree_centrality(G)

            # Convert to string keys for JSON serialization
            centrality_values = {str(k): float(v)
                                 for k, v in centrality.items()}

            logger.info(
                f"Calculated degree centrality for {len(centrality_values)} nodes")

            return {
                "success": True,
                "centrality_type": "degree",
                "values": centrality_values,
                "statistics": {
                    "min": min(centrality_values.values()),
                    "max": max(centrality_values.values()),
                    "mean": sum(centrality_values.values()) / len(centrality_values)
                }
            }

        except Exception as e:
            error_msg = f"Failed to calculate degree centrality: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def calculate_betweenness_centrality(
        graphml_content: str,
        normalized: bool = True,
        k: Optional[int] = None,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Calculate betweenness centrality for all nodes in the graph.

        Args:
            graphml_content: GraphML content as string
            normalized: If True, normalize to [0,1] range
            k: Number of nodes to use for approximation (None for exact)

        Returns:
            Dictionary containing centrality values for each node
        """
        try:
            G = parse_graphml_content(graphml_content)
            centrality = nx.betweenness_centrality(
                G, normalized=normalized, k=k)

            centrality_values = {str(k): float(v)
                                 for k, v in centrality.items()}

            logger.info(
                f"Calculated betweenness centrality for {len(centrality_values)} nodes")

            return {
                "success": True,
                "centrality_type": "betweenness",
                "values": centrality_values,
                "parameters": {
                    "normalized": normalized,
                    "k": k
                },
                "statistics": {
                    "min": min(centrality_values.values()),
                    "max": max(centrality_values.values()),
                    "mean": sum(centrality_values.values()) / len(centrality_values)
                }
            }

        except Exception as e:
            error_msg = f"Failed to calculate betweenness centrality: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def calculate_closeness_centrality(
        graphml_content: str,
        normalized: bool = True,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Calculate closeness centrality for all nodes in the graph.

        Args:
            graphml_content: GraphML content as string
            normalized: If True, normalize to [0,1] range

        Returns:
            Dictionary containing centrality values for each node
        """
        try:
            G = parse_graphml_content(graphml_content)
            centrality = nx.closeness_centrality(G, normalized=normalized)

            centrality_values = {str(k): float(v)
                                 for k, v in centrality.items()}

            logger.info(
                f"Calculated closeness centrality for {len(centrality_values)} nodes")

            return {
                "success": True,
                "centrality_type": "closeness",
                "values": centrality_values,
                "parameters": {
                    "normalized": normalized
                },
                "statistics": {
                    "min": min(centrality_values.values()),
                    "max": max(centrality_values.values()),
                    "mean": sum(centrality_values.values()) / len(centrality_values)
                }
            }

        except Exception as e:
            error_msg = f"Failed to calculate closeness centrality: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def calculate_eigenvector_centrality(
        graphml_content: str,
        max_iter: int = 100,
        tol: float = 1e-6,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Calculate eigenvector centrality for all nodes in the graph.

        Args:
            graphml_content: GraphML content as string
            max_iter: Maximum number of iterations
            tol: Tolerance for convergence

        Returns:
            Dictionary containing centrality values for each node
        """
        try:
            G = parse_graphml_content(graphml_content)

            # Check if graph is connected (eigenvector centrality requires connectivity)
            if not nx.is_connected(G):
                # For disconnected graphs, calculate for largest component
                largest_cc = max(nx.connected_components(G), key=len)
                G_cc = G.subgraph(largest_cc).copy()
                centrality_cc = nx.eigenvector_centrality(
                    G_cc, max_iter=max_iter, tol=tol)

                # Add zeros for nodes not in largest component
                centrality = {node: 0.0 for node in G.nodes()}
                centrality.update(centrality_cc)
            else:
                centrality = nx.eigenvector_centrality(
                    G, max_iter=max_iter, tol=tol)

            centrality_values = {str(k): float(v)
                                 for k, v in centrality.items()}

            logger.info(
                f"Calculated eigenvector centrality for {len(centrality_values)} nodes")

            return {
                "success": True,
                "centrality_type": "eigenvector",
                "values": centrality_values,
                "parameters": {
                    "max_iter": max_iter,
                    "tol": tol
                },
                "statistics": {
                    "min": min(centrality_values.values()),
                    "max": max(centrality_values.values()),
                    "mean": sum(centrality_values.values()) / len(centrality_values)
                }
            }

        except Exception as e:
            error_msg = f"Failed to calculate eigenvector centrality: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def calculate_pagerank(
        graphml_content: str,
        alpha: float = 0.85,
        max_iter: int = 100,
        tol: float = 1e-6,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Calculate PageRank centrality for all nodes in the graph.

        Args:
            graphml_content: GraphML content as string
            alpha: Damping parameter (probability of following a link)
            max_iter: Maximum number of iterations
            tol: Tolerance for convergence

        Returns:
            Dictionary containing PageRank values for each node
        """
        try:
            G = parse_graphml_content(graphml_content)
            centrality = nx.pagerank(
                G, alpha=alpha, max_iter=max_iter, tol=tol)

            centrality_values = {str(k): float(v)
                                 for k, v in centrality.items()}

            logger.info(
                f"Calculated PageRank for {len(centrality_values)} nodes")

            return {
                "success": True,
                "centrality_type": "pagerank",
                "values": centrality_values,
                "parameters": {
                    "alpha": alpha,
                    "max_iter": max_iter,
                    "tol": tol
                },
                "statistics": {
                    "min": min(centrality_values.values()),
                    "max": max(centrality_values.values()),
                    "mean": sum(centrality_values.values()) / len(centrality_values)
                }
            }

        except Exception as e:
            error_msg = f"Failed to calculate PageRank: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def get_available_centrality_measures() -> Dict[str, Any]:
        """
        Get list of available centrality measures with descriptions.

        Returns:
            Dictionary containing available centrality measures and their descriptions
        """
        measures = {
            "degree": {
                "name": "Degree Centrality",
                "description": "Number of connections a node has",
                "parameters": [],
                "computational_complexity": "O(V)",
                "best_for": "Identifying highly connected nodes"
            },
            "betweenness": {
                "name": "Betweenness Centrality",
                "description": "Frequency a node appears on shortest paths",
                "parameters": ["normalized", "k"],
                "computational_complexity": "O(V³)",
                "best_for": "Identifying bridge nodes and bottlenecks"
            },
            "closeness": {
                "name": "Closeness Centrality",
                "description": "Average distance to all other nodes",
                "parameters": ["normalized"],
                "computational_complexity": "O(V²)",
                "best_for": "Identifying nodes with fast access to network"
            },
            "eigenvector": {
                "name": "Eigenvector Centrality",
                "description": "Influence based on connections to high-scoring nodes",
                "parameters": ["max_iter", "tol"],
                "computational_complexity": "O(V²)",
                "best_for": "Identifying influential nodes in connected networks"
            },
            "pagerank": {
                "name": "PageRank",
                "description": "Google's PageRank algorithm",
                "parameters": ["alpha", "max_iter", "tol"],
                "computational_complexity": "O(V²)",
                "best_for": "Ranking nodes by importance with damping"
            }
        }

        return {
            "success": True,
            "measures": measures
        }
