"""
Cache resource endpoints for the MCP server.
Provides read-only access to cache statistics and management information.
"""

import logging
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from core.context import ServerContext

logger = logging.getLogger("networkx_mcp.resources.cache")


def register_cache_resources(mcp: FastMCP):
    """Register cache resource endpoints with the MCP server."""

    @mcp.resource("cache://stats")
    def get_cache_statistics(
        ctx: Context[ServerSession, ServerContext] = None
    ) -> str:
        """
        Get cache statistics and usage information.

        Returns:
            JSON string containing cache statistics
        """
        try:
            if not ctx:
                return '{"error": "No context available"}'

            context = ctx.request_context.lifespan_context
            stats = context.get_cache_stats()

            # Add more detailed statistics
            detailed_stats = {
                "basic_stats": stats,
                "graph_cache": {
                    "total_graphs": len(context.graph_cache),
                    "graph_ids": list(context.graph_cache.keys())
                },
                "centrality_cache": {
                    "total_calculations": len(context.centrality_cache),
                    "calculation_ids": list(context.centrality_cache.keys())
                },
                "memory_info": {
                    "approximate_memory_usage": "Not implemented",
                    "cache_hit_rate": "Not implemented"
                }
            }

            logger.info("Retrieved cache statistics")
            return str(detailed_stats)

        except Exception as e:
            error_msg = f"Failed to retrieve cache statistics: {str(e)}"
            logger.error(error_msg)
            return f'{{"error": "{error_msg}"}}'

    @mcp.resource("cache://centrality")
    def get_centrality_cache_info(
        ctx: Context[ServerSession, ServerContext] = None
    ) -> str:
        """
        Get information about cached centrality calculations.

        Returns:
            JSON string containing centrality cache information
        """
        try:
            if not ctx:
                return '{"error": "No context available"}'

            cache = ctx.request_context.lifespan_context.centrality_cache

            calculations = []
            for calc_id, calc_data in cache.items():
                calculations.append({
                    "calculation_id": calc_id,
                    "centrality_type": calc_data.get("centrality_type"),
                    "graph_info": calc_data.get("graph_info", {}),
                    "created_at": calc_data.get("created_at"),
                    "node_count": len(calc_data.get("centrality_values", {}))
                })

            result = {
                "centrality_calculations": calculations,
                "total_calculations": len(calculations)
            }

            logger.info(
                f"Retrieved centrality cache info for {len(calculations)} calculations")
            return str(result)

        except Exception as e:
            error_msg = f"Failed to retrieve centrality cache info: {str(e)}"
            logger.error(error_msg)
            return f'{{"error": "{error_msg}"}}'

    @mcp.resource("cache://history")
    def get_calculation_history(
        ctx: Context[ServerSession, ServerContext] = None
    ) -> str:
        """
        Get calculation history and audit trail.

        Returns:
            JSON string containing calculation history
        """
        try:
            if not ctx:
                return '{"error": "No context available"}'

            history = ctx.request_context.lifespan_context.calculation_history

            history_list = []
            for entry_id, entry_data in history.items():
                history_list.append({
                    "entry_id": entry_id,
                    "operation": entry_data.get("operation"),
                    "timestamp": entry_data.get("timestamp"),
                    "parameters": entry_data.get("parameters", {}),
                    "success": entry_data.get("success", False),
                    "duration": entry_data.get("duration")
                })

            # Sort by timestamp (newest first)
            history_list.sort(key=lambda x: x.get(
                "timestamp", ""), reverse=True)

            result = {
                "calculation_history": history_list,
                "total_entries": len(history_list)
            }

            logger.info(
                f"Retrieved calculation history with {len(history_list)} entries")
            return str(result)

        except Exception as e:
            error_msg = f"Failed to retrieve calculation history: {str(e)}"
            logger.error(error_msg)
            return f'{{"error": "{error_msg}"}}'
