"""
Graph I/O tools for the MCP server.
Handles import, export, and format conversion operations.
"""

import logging
from typing import Dict, Any, Optional
import networkx as nx
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from core.context import ServerContext
from core.graph_utils import parse_graphml_content, graph_to_graphml_string, validate_graph

logger = logging.getLogger("networkx_mcp.tools.graph_io")


def register_io_tools(mcp: FastMCP):
    """Register graph I/O tools with the MCP server."""

    @mcp.tool()
    def import_graphml(
        graphml_content: str,
        validate: bool = True,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Import and validate GraphML content.

        Args:
            graphml_content: GraphML content as string
            validate: Whether to perform validation checks

        Returns:
            Dictionary containing import results and graph information
        """
        try:
            G = parse_graphml_content(graphml_content)

            result = {
                "success": True,
                "message": "GraphML imported successfully"
            }

            if validate:
                validation_result = validate_graph(G)
                result.update({
                    "validation": validation_result,
                    "graph_info": {
                        "nodes": G.number_of_nodes(),
                        "edges": G.number_of_edges(),
                        "node_attributes": list(set().union(*(d.keys() for n, d in G.nodes(data=True)))),
                        "edge_attributes": list(set().union(*(d.keys() for u, v, d in G.edges(data=True))))
                    }
                })

            logger.info(
                f"Imported GraphML with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

            return result

        except Exception as e:
            error_msg = f"Failed to import GraphML: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def export_to_graphml(
        graphml_content: str,
        include_positions: bool = True,
        pretty_print: bool = True,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Export graph to GraphML format with options.

        Args:
            graphml_content: Input GraphML content as string
            include_positions: Whether to include node position data
            pretty_print: Whether to format the XML nicely

        Returns:
            Dictionary containing the exported GraphML content
        """
        try:
            G = parse_graphml_content(graphml_content)

            # Create a copy for export modifications
            G_export = G.copy()

            if not include_positions:
                # Remove position attributes
                for node in G_export.nodes():
                    for attr in ['x', 'y', 'z']:
                        if attr in G_export.nodes[node]:
                            del G_export.nodes[node][attr]

            exported_graphml = graph_to_graphml_string(G_export)

            logger.info("Exported graph to GraphML format")

            return {
                "success": True,
                "graphml_content": exported_graphml,
                "export_info": {
                    "nodes": G_export.number_of_nodes(),
                    "edges": G_export.number_of_edges(),
                    "includes_positions": include_positions,
                    "pretty_print": pretty_print
                }
            }

        except Exception as e:
            error_msg = f"Failed to export to GraphML: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def convert_to_adjacency_list(
        graphml_content: str,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Convert graph to adjacency list representation.

        Args:
            graphml_content: GraphML content as string

        Returns:
            Dictionary containing the adjacency list representation
        """
        try:
            G = parse_graphml_content(graphml_content)

            # Create adjacency list
            adj_list = {}
            for node in G.nodes():
                neighbors = list(G.neighbors(node))
                adj_list[str(node)] = [str(n) for n in neighbors]

            logger.info(
                f"Converted graph to adjacency list with {len(adj_list)} nodes")

            return {
                "success": True,
                "adjacency_list": adj_list,
                "format": "adjacency_list",
                "graph_info": {
                    "nodes": len(adj_list),
                    "edges": G.number_of_edges(),
                    "directed": G.is_directed()
                }
            }

        except Exception as e:
            error_msg = f"Failed to convert to adjacency list: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def convert_to_edge_list(
        graphml_content: str,
        include_attributes: bool = False,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Convert graph to edge list representation.

        Args:
            graphml_content: GraphML content as string
            include_attributes: Whether to include edge attributes

        Returns:
            Dictionary containing the edge list representation
        """
        try:
            G = parse_graphml_content(graphml_content)

            edge_list = []
            for u, v, data in G.edges(data=True):
                edge = {"source": str(u), "target": str(v)}
                if include_attributes and data:
                    edge["attributes"] = data
                edge_list.append(edge)

            logger.info(
                f"Converted graph to edge list with {len(edge_list)} edges")

            return {
                "success": True,
                "edge_list": edge_list,
                "format": "edge_list",
                "graph_info": {
                    "nodes": G.number_of_nodes(),
                    "edges": len(edge_list),
                    "directed": G.is_directed(),
                    "includes_attributes": include_attributes
                }
            }

        except Exception as e:
            error_msg = f"Failed to convert to edge list: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def get_graph_statistics(
        graphml_content: str,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the graph.

        Args:
            graphml_content: GraphML content as string

        Returns:
            Dictionary containing detailed graph statistics
        """
        try:
            G = parse_graphml_content(graphml_content)

            stats = {
                "basic": {
                    "nodes": G.number_of_nodes(),
                    "edges": G.number_of_edges(),
                    "directed": G.is_directed(),
                    "density": float(nx.density(G))
                },
                "connectivity": {
                    "is_connected": nx.is_connected(G) if not G.is_directed() else nx.is_strongly_connected(G),
                    "number_of_components": nx.number_connected_components(G) if not G.is_directed() else nx.number_strongly_connected_components(G)
                },
                "degree": {
                    "average_degree": float(sum(dict(G.degree()).values()) / G.number_of_nodes()) if G.number_of_nodes() > 0 else 0,
                    "max_degree": max(dict(G.degree()).values()) if G.number_of_nodes() > 0 else 0,
                    "min_degree": min(dict(G.degree()).values()) if G.number_of_nodes() > 0 else 0
                }
            }

            # Add additional metrics for connected graphs
            if G.number_of_nodes() > 0:
                if nx.is_connected(G):
                    stats["path_metrics"] = {
                        "diameter": nx.diameter(G),
                        "radius": nx.radius(G),
                        "average_shortest_path_length": float(nx.average_shortest_path_length(G))
                    }

                # Clustering coefficient
                stats["clustering"] = {
                    "average_clustering": float(nx.average_clustering(G)),
                    "transitivity": float(nx.transitivity(G))
                }

            logger.info("Calculated comprehensive graph statistics")

            return {
                "success": True,
                "statistics": stats
            }

        except Exception as e:
            error_msg = f"Failed to calculate graph statistics: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
