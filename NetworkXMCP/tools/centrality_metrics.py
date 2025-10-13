"""
Centrality metrics calculation tools for the MCP server.
Handles various centrality measures and network analysis metrics.
Enhanced with MCP best practices.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Handle imports with fallbacks
try:
    import networkx as nx
except ImportError:
    # Mock for development
    class nx:
        @staticmethod
        def degree_centrality(G): return {}
        @staticmethod
        def betweenness_centrality(G, **kwargs): return {}
        @staticmethod
        def closeness_centrality(G, **kwargs): return {}
        @staticmethod
        def eigenvector_centrality_numpy(G, **kwargs): return {}
        @staticmethod
        def pagerank(G, **kwargs): return {}
        @staticmethod
        def density(G): return 0.5
        @staticmethod
        def connected_components(G): return []

try:
    from mcp.server.fastmcp import FastMCP, Context
    from mcp.server.session import ServerSession
except ImportError:
    # Mock for development
    class FastMCP:
        def tool(self): return lambda f: f

    class Context:
        pass

    class ServerSession:
        pass

from core.context import ServerContext
from core.graph_utils import parse_graphml_content

logger = logging.getLogger("networkx_mcp.tools.centrality")


def register_centrality_tools(mcp: FastMCP):
    """Register centrality calculation tools with the MCP server following MCP best practices."""

    @mcp.tool()
    def calculate_degree_centrality(
        graphml_content: str,
        normalized: bool = True,
        store_result: bool = False,
        calculation_id: Optional[str] = None,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Calculate degree centrality for all nodes in the graph.

        Enhanced with MCP best practices:
        - Structured input/output schemas
        - Optional result caching
        - Comprehensive error handling with codes
        - Detailed metadata and statistics

        Args:
            graphml_content: GraphML content as string
            normalized: Whether to normalize centrality values
            store_result: Whether to cache the calculation result
            calculation_id: Optional ID for storing the calculation

        Returns:
            Structured response with centrality values, metadata, and statistics
        """
        try:
            # Validate input
            if not graphml_content or not graphml_content.strip():
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "GraphML content cannot be empty",
                        "timestamp": datetime.now().isoformat()
                    }
                }

            # Parse graph with error handling
            try:
                G = parse_graphml_content(graphml_content)
            except Exception as parse_error:
                logger.error(f"GraphML parsing failed: {parse_error}")
                return {
                    "success": False,
                    "error": {
                        "code": "PARSE_ERROR",
                        "message": f"Failed to parse GraphML: {str(parse_error)}",
                        "timestamp": datetime.now().isoformat()
                    }
                }

            # Calculate centrality with validation
            if G.number_of_nodes() == 0:
                return {
                    "success": False,
                    "error": {
                        "code": "EMPTY_GRAPH",
                        "message": "Graph contains no nodes",
                        "timestamp": datetime.now().isoformat()
                    }
                }

            centrality = nx.degree_centrality(
                G) if normalized else dict(G.degree())

            # Convert to string keys for JSON serialization
            centrality_values = {str(k): float(v)
                                 for k, v in centrality.items()}

            # Calculate comprehensive statistics
            values = list(centrality_values.values())
            statistics = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / len(values),
                "median": sorted(values)[len(values) // 2] if values else 0,
                "sum": sum(values)
            }

            # Generate calculation metadata
            calc_id = calculation_id or f"deg_{uuid.uuid4().hex[:8]}"
            metadata = {
                "calculation_id": calc_id,
                "algorithm": "degree_centrality",
                "parameters": {"normalized": normalized},
                "graph_info": {
                    "nodes": G.number_of_nodes(),
                    "edges": G.number_of_edges(),
                    "is_directed": G.is_directed() if hasattr(G, 'is_directed') else False,
                    "density": nx.density(G) if hasattr(nx, 'density') else None
                },
                "timestamp": datetime.now().isoformat()
            }

            # Store result in cache if requested and context available
            if store_result and ctx:
                try:
                    context = ctx.request_context.lifespan_context
                    context.centrality_cache[calc_id] = {
                        "centrality_type": "degree",
                        "values": centrality_values,
                        "statistics": statistics,
                        "metadata": metadata
                    }
                    logger.info(
                        f"Stored degree centrality calculation: {calc_id}")
                except Exception as cache_error:
                    logger.warning(f"Failed to cache result: {cache_error}")

            logger.info(
                f"Calculated degree centrality for {len(centrality_values)} nodes (normalized={normalized})")

            # Structured response following MCP best practices
            return {
                "success": True,
                "data": {
                    "centrality_type": "degree",
                    "values": centrality_values,
                    "statistics": statistics,
                    "metadata": metadata,
                    "cached": store_result and ctx is not None
                },
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            error_msg = f"Unexpected error calculating degree centrality: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
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
