"""
Graph resource endpoints for the MCP server.
Provides read-only access to cached graphs and graph metadata.
"""

import logging
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from core.context import ServerContext

logger = logging.getLogger("networkx_mcp.resources.graphs")


def register_graph_resources(mcp: FastMCP):
    """Register graph resource endpoints with the MCP server."""

    @mcp.resource("graph://cached/{graph_id}")
    def get_cached_graph(
        graph_id: str,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> str:
        """
        Get a cached graph by ID.

        Args:
            graph_id: Unique identifier for the cached graph

        Returns:
            JSON string containing the cached graph data
        """
        try:
            if not ctx:
                return '{"error": "No context available"}'

            cache = ctx.request_context.lifespan_context.graph_cache

            if graph_id not in cache:
                return f'{{"error": "Graph {graph_id} not found in cache"}}'

            graph_data = cache[graph_id]

            # Return graph metadata and basic info
            result = {
                "graph_id": graph_id,
                "metadata": graph_data.get("metadata", {}),
                "nodes": graph_data.get("nodes", 0),
                "edges": graph_data.get("edges", 0),
                "created_at": graph_data.get("created_at"),
                "layout_applied": graph_data.get("layout_type"),
                "available_metrics": list(graph_data.get("metrics", {}).keys())
            }

            logger.info(f"Retrieved cached graph: {graph_id}")
            return str(result)

        except Exception as e:
            error_msg = f"Failed to retrieve cached graph {graph_id}: {str(e)}"
            logger.error(error_msg)
            return f'{{"error": "{error_msg}"}}'

    @mcp.resource("graph://list")
    def list_cached_graphs(
        ctx: Context[ServerSession, ServerContext] = None
    ) -> str:
        """
        List all cached graphs.

        Returns:
            JSON string containing list of cached graph IDs and metadata
        """
        try:
            if not ctx:
                return '{"error": "No context available"}'

            cache = ctx.request_context.lifespan_context.graph_cache

            graphs_list = []
            for graph_id, graph_data in cache.items():
                graphs_list.append({
                    "graph_id": graph_id,
                    "nodes": graph_data.get("nodes", 0),
                    "edges": graph_data.get("edges", 0),
                    "created_at": graph_data.get("created_at"),
                    "layout_type": graph_data.get("layout_type"),
                    "metrics_count": len(graph_data.get("metrics", {}))
                })

            result = {
                "cached_graphs": graphs_list,
                "total_count": len(graphs_list)
            }

            logger.info(f"Listed {len(graphs_list)} cached graphs")
            return str(result)

        except Exception as e:
            error_msg = f"Failed to list cached graphs: {str(e)}"
            logger.error(error_msg)
            return f'{{"error": "{error_msg}"}}'

    @mcp.resource("graph://metrics/{graph_id}")
    def get_graph_metrics(
        graph_id: str,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> str:
        """
        Get computed metrics for a cached graph.

        Args:
            graph_id: Unique identifier for the cached graph

        Returns:
            JSON string containing the computed metrics
        """
        try:
            if not ctx:
                return '{"error": "No context available"}'

            cache = ctx.request_context.lifespan_context.graph_cache

            if graph_id not in cache:
                return f'{{"error": "Graph {graph_id} not found in cache"}}'

            graph_data = cache[graph_id]
            metrics = graph_data.get("metrics", {})

            result = {
                "graph_id": graph_id,
                "metrics": metrics,
                "available_metrics": list(metrics.keys()),
                "computed_at": graph_data.get("metrics_computed_at")
            }

            logger.info(f"Retrieved metrics for graph: {graph_id}")
            return str(result)

        except Exception as e:
            error_msg = f"Failed to retrieve metrics for graph {graph_id}: {str(e)}"
            logger.error(error_msg)
            return f'{{"error": "{error_msg}"}}'

    @mcp.resource("graph://graphml/{graph_id}")
    def get_graph_graphml(
        graph_id: str,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> str:
        """
        Get GraphML content for a cached graph.

        Args:
            graph_id: Unique identifier for the cached graph

        Returns:
            GraphML content as string
        """
        try:
            if not ctx:
                return '{"error": "No context available"}'

            cache = ctx.request_context.lifespan_context.graph_cache

            if graph_id not in cache:
                return f'{{"error": "Graph {graph_id} not found in cache"}}'

            graph_data = cache[graph_id]
            graphml_content = graph_data.get("graphml_content", "")

            if not graphml_content:
                return f'{{"error": "No GraphML content available for graph {graph_id}"}}'

            logger.info(f"Retrieved GraphML content for graph: {graph_id}")
            return graphml_content

        except Exception as e:
            error_msg = f"Failed to retrieve GraphML for graph {graph_id}: {str(e)}"
            logger.error(error_msg)
            return f'{{"error": "{error_msg}"}}'
