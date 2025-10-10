"""
Layout algorithm tools for the MCP server.
Handles various graph layout algorithms and positioning.
"""

import logging
from typing import Dict, Any, Optional, Union
import networkx as nx
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from core.context import ServerContext
from core.graph_utils import parse_graphml_content, graph_to_graphml_string

logger = logging.getLogger("networkx_mcp.tools.layout")


def register_layout_tools(mcp: FastMCP):
    """Register layout algorithm tools with the MCP server."""

    @mcp.tool()
    def apply_spring_layout(
        graphml_content: str,
        k: Optional[float] = None,
        iterations: int = 50,
        seed: Optional[int] = None,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Apply spring layout (Fruchterman-Reingold) to the graph.

        Args:
            graphml_content: GraphML content as string
            k: Optimal distance between nodes (default: auto)
            iterations: Number of iterations (default: 50)
            seed: Random seed for reproducibility

        Returns:
            Dictionary containing positions and updated GraphML
        """
        try:
            G = parse_graphml_content(graphml_content)

            # Apply spring layout
            pos = nx.spring_layout(
                G,
                k=k,
                iterations=iterations,
                seed=seed
            )

            # Convert positions to JSON-serializable format
            positions = {
                str(node): {"x": float(coord[0]), "y": float(coord[1])}
                for node, coord in pos.items()
            }

            # Add positions to graph
            for node, coord in pos.items():
                G.nodes[node]['x'] = float(coord[0])
                G.nodes[node]['y'] = float(coord[1])

            updated_graphml = graph_to_graphml_string(G)

            logger.info(f"Applied spring layout with {iterations} iterations")

            return {
                "success": True,
                "layout_type": "spring",
                "positions": positions,
                "graphml_content": updated_graphml,
                "parameters": {
                    "k": k,
                    "iterations": iterations,
                    "seed": seed
                }
            }

        except Exception as e:
            error_msg = f"Failed to apply spring layout: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def apply_circular_layout(
        graphml_content: str,
        scale: float = 1.0,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Apply circular layout to the graph.

        Args:
            graphml_content: GraphML content as string
            scale: Scale factor for positions

        Returns:
            Dictionary containing positions and updated GraphML
        """
        try:
            G = parse_graphml_content(graphml_content)

            pos = nx.circular_layout(G, scale=scale)

            positions = {
                str(node): {"x": float(coord[0]), "y": float(coord[1])}
                for node, coord in pos.items()
            }

            # Add positions to graph
            for node, coord in pos.items():
                G.nodes[node]['x'] = float(coord[0])
                G.nodes[node]['y'] = float(coord[1])

            updated_graphml = graph_to_graphml_string(G)

            logger.info("Applied circular layout")

            return {
                "success": True,
                "layout_type": "circular",
                "positions": positions,
                "graphml_content": updated_graphml,
                "parameters": {
                    "scale": scale
                }
            }

        except Exception as e:
            error_msg = f"Failed to apply circular layout: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def apply_hierarchical_layout(
        graphml_content: str,
        root: Optional[str] = None,
        orientation: str = "top-down",
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Apply hierarchical layout to the graph (works best with trees/DAGs).

        Args:
            graphml_content: GraphML content as string
            root: Root node for hierarchy (if None, use node with highest degree)
            orientation: Layout orientation ('top-down', 'left-right')

        Returns:
            Dictionary containing positions and updated GraphML
        """
        try:
            G = parse_graphml_content(graphml_content)

            # If no root specified, find node with highest degree
            if root is None:
                root = max(G.nodes(), key=lambda x: G.degree(x))

            # Try to create a spanning tree if graph is not already a tree
            if not nx.is_tree(G):
                tree = nx.minimum_spanning_tree(G.to_undirected())
            else:
                tree = G

            # Apply layout based on orientation
            if orientation == "top-down":
                pos = nx.spring_layout(tree, k=2.0, iterations=100)
                # Adjust y-coordinates based on distance from root
                try:
                    distances = nx.single_source_shortest_path_length(
                        tree, root)
                    max_dist = max(distances.values()) if distances else 0
                    for node in pos:
                        dist = distances.get(node, 0)
                        pos[node] = (pos[node][0], 1.0 -
                                     (dist / max_dist if max_dist > 0 else 0))
                except:
                    # Fallback to regular spring layout
                    pass
            else:  # left-right
                pos = nx.spring_layout(tree, k=2.0, iterations=100)
                try:
                    distances = nx.single_source_shortest_path_length(
                        tree, root)
                    max_dist = max(distances.values()) if distances else 0
                    for node in pos:
                        dist = distances.get(node, 0)
                        pos[node] = (dist / max_dist if max_dist >
                                     0 else 0, pos[node][1])
                except:
                    pass

            positions = {
                str(node): {"x": float(coord[0]), "y": float(coord[1])}
                for node, coord in pos.items()
            }

            # Add positions to graph
            for node, coord in pos.items():
                G.nodes[node]['x'] = float(coord[0])
                G.nodes[node]['y'] = float(coord[1])

            updated_graphml = graph_to_graphml_string(G)

            logger.info(
                f"Applied hierarchical layout with root={root}, orientation={orientation}")

            return {
                "success": True,
                "layout_type": "hierarchical",
                "positions": positions,
                "graphml_content": updated_graphml,
                "parameters": {
                    "root": str(root),
                    "orientation": orientation
                }
            }

        except Exception as e:
            error_msg = f"Failed to apply hierarchical layout: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def get_available_layouts() -> Dict[str, Any]:
        """
        Get list of available layout algorithms with descriptions.

        Returns:
            Dictionary containing available layouts and their descriptions
        """
        layouts = {
            "spring": {
                "name": "Spring Layout (Fruchterman-Reingold)",
                "description": "Force-directed layout with spring simulation",
                "parameters": ["k", "iterations", "seed"],
                "best_for": "General purpose, small to medium graphs"
            },
            "circular": {
                "name": "Circular Layout",
                "description": "Arranges nodes in a circle",
                "parameters": ["scale"],
                "best_for": "Small graphs, highlighting connectivity patterns"
            },
            "hierarchical": {
                "name": "Hierarchical Layout",
                "description": "Tree-like layout with levels",
                "parameters": ["root", "orientation"],
                "best_for": "Trees, DAGs, hierarchical structures"
            }
        }

        return {
            "success": True,
            "layouts": layouts
        }
