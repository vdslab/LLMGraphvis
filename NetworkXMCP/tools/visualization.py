"""
Visualization tools for the MCP server.
Handles color schemes, node sizing, and visual formatting.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from core.context import ServerContext
from core.graph_utils import parse_graphml_content, create_cytoscape_data

logger = logging.getLogger("networkx_mcp.tools.visualization")


def generate_color_scale(values: List[float], color_scheme: str = "viridis") -> List[str]:
    """Generate color scale for values."""
    if not values:
        return []

    min_val, max_val = min(values), max(values)
    if min_val == max_val:
        # All values are the same
        return ["#4287f5"] * len(values)

    # Normalize values to 0-1 range
    normalized = [(v - min_val) / (max_val - min_val) for v in values]

    # Color schemes
    color_schemes = {
        "viridis": ["#440154", "#31688e", "#35b779", "#fde725"],
        "plasma": ["#0d0887", "#7e03a8", "#cc4778", "#f89441", "#f0f921"],
        "blues": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
        "reds": ["#fff5f0", "#fcbba1", "#fb6a4a", "#cb181d", "#67000d"],
        "greens": ["#f7fcf5", "#c7e9c0", "#74c476", "#238b45", "#00441b"]
    }

    scheme_colors = color_schemes.get(color_scheme, color_schemes["viridis"])

    # Simple linear interpolation for color mapping
    colors = []
    for norm_val in normalized:
        idx = min(int(norm_val * (len(scheme_colors) - 1)),
                  len(scheme_colors) - 1)
        colors.append(scheme_colors[idx])

    return colors


def calculate_node_sizes(values: List[float], size_range: Tuple[float, float] = (5, 20)) -> List[float]:
    """Calculate node sizes based on values."""
    if not values:
        return []

    min_val, max_val = min(values), max(values)
    if min_val == max_val:
        # All values are the same
        avg_size = (size_range[0] + size_range[1]) / 2
        return [avg_size] * len(values)

    # Normalize and scale
    normalized = [(v - min_val) / (max_val - min_val) for v in values]
    sizes = [size_range[0] + norm_val *
             (size_range[1] - size_range[0]) for norm_val in normalized]

    return sizes


def register_visualization_tools(mcp: FastMCP):
    """Register visualization tools with the MCP server."""

    @mcp.tool()
    def create_visualization_data(
        graphml_content: str,
        metric_values: Optional[Dict[str, float]] = None,
        color_scheme: str = "viridis",
        size_range: List[float] = [5, 20],
        layout_positions: Optional[Dict[str, Dict[str, float]]] = None,
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Create visualization data for a graph with optional metric coloring/sizing.

        Args:
            graphml_content: GraphML content as string
            metric_values: Dictionary mapping node IDs to metric values
            color_scheme: Color scheme name (viridis, plasma, blues, reds, greens)
            size_range: Node size range [min, max]
            layout_positions: Optional node positions

        Returns:
            Dictionary containing Cytoscape.js formatted data with styling
        """
        try:
            G = parse_graphml_content(graphml_content)

            # Create base cytoscape data
            cyto_data = create_cytoscape_data(G, layout_positions)

            # Apply metric-based styling if provided
            if metric_values:
                node_ids = [str(node) for node in G.nodes()]
                values = [metric_values.get(node_id, 0.0)
                          for node_id in node_ids]

                colors = generate_color_scale(values, color_scheme)
                sizes = calculate_node_sizes(values, tuple(size_range))

                # Update node data with styling
                for i, node in enumerate(cyto_data["nodes"]):
                    node_id = node["data"]["id"]
                    if node_id in metric_values:
                        node["data"]["value"] = metric_values[node_id]
                        node["style"] = {
                            "background-color": colors[i],
                            "width": sizes[i],
                            "height": sizes[i]
                        }

            logger.info(
                f"Created visualization data for {len(cyto_data['nodes'])} nodes")

            return {
                "success": True,
                "visualization_data": cyto_data,
                "styling_info": {
                    "color_scheme": color_scheme,
                    "size_range": size_range,
                    "has_metric_values": metric_values is not None,
                    "has_positions": layout_positions is not None
                }
            }

        except Exception as e:
            error_msg = f"Failed to create visualization data: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def get_color_schemes() -> Dict[str, Any]:
        """
        Get available color schemes for visualization.

        Returns:
            Dictionary containing available color schemes and their descriptions
        """
        schemes = {
            "viridis": {
                "name": "Viridis",
                "description": "Perceptually uniform blue-green-yellow scale",
                "colors": ["#440154", "#31688e", "#35b779", "#fde725"],
                "best_for": "General purpose, colorblind-friendly"
            },
            "plasma": {
                "name": "Plasma",
                "description": "Perceptually uniform purple-pink-yellow scale",
                "colors": ["#0d0887", "#7e03a8", "#cc4778", "#f89441", "#f0f921"],
                "best_for": "High contrast visualization"
            },
            "blues": {
                "name": "Blues",
                "description": "Sequential blue color scale",
                "colors": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
                "best_for": "Water, cold, or intensity themes"
            },
            "reds": {
                "name": "Reds",
                "description": "Sequential red color scale",
                "colors": ["#fff5f0", "#fcbba1", "#fb6a4a", "#cb181d", "#67000d"],
                "best_for": "Heat, danger, or importance themes"
            },
            "greens": {
                "name": "Greens",
                "description": "Sequential green color scale",
                "colors": ["#f7fcf5", "#c7e9c0", "#74c476", "#238b45", "#00441b"],
                "best_for": "Nature, growth, or positive themes"
            }
        }

        return {
            "success": True,
            "color_schemes": schemes
        }

    @mcp.tool()
    def apply_metric_styling(
        cytoscape_data: Dict[str, Any],
        metric_values: Dict[str, float],
        color_scheme: str = "viridis",
        size_range: List[float] = [5, 20],
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Apply metric-based styling to existing Cytoscape data.

        Args:
            cytoscape_data: Existing Cytoscape.js data structure
            metric_values: Dictionary mapping node IDs to metric values
            color_scheme: Color scheme name
            size_range: Node size range [min, max]

        Returns:
            Dictionary containing styled Cytoscape.js data
        """
        try:
            # Make a copy to avoid modifying original data
            styled_data = {
                "nodes": [node.copy() for node in cytoscape_data["nodes"]],
                "edges": [edge.copy() for edge in cytoscape_data["edges"]]
            }

            # Extract metric values for nodes that exist in the data
            node_ids = [node["data"]["id"] for node in styled_data["nodes"]]
            values = [metric_values.get(node_id, 0.0) for node_id in node_ids]

            colors = generate_color_scale(values, color_scheme)
            sizes = calculate_node_sizes(values, tuple(size_range))

            # Apply styling
            for i, node in enumerate(styled_data["nodes"]):
                node_id = node["data"]["id"]
                if node_id in metric_values:
                    node["data"]["value"] = metric_values[node_id]
                    node["style"] = {
                        "background-color": colors[i],
                        "width": sizes[i],
                        "height": sizes[i]
                    }

            logger.info(
                f"Applied metric styling to {len(styled_data['nodes'])} nodes")

            return {
                "success": True,
                "styled_data": styled_data,
                "styling_info": {
                    "color_scheme": color_scheme,
                    "size_range": size_range,
                    "nodes_styled": len([n for n in node_ids if n in metric_values])
                }
            }

        except Exception as e:
            error_msg = f"Failed to apply metric styling: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool()
    def create_legend_data(
        metric_values: Dict[str, float],
        color_scheme: str = "viridis",
        size_range: List[float] = [5, 20],
        ctx: Context[ServerSession, ServerContext] = None
    ) -> Dict[str, Any]:
        """
        Create legend data for metric visualization.

        Args:
            metric_values: Dictionary mapping node IDs to metric values
            color_scheme: Color scheme name
            size_range: Node size range [min, max]

        Returns:
            Dictionary containing legend information
        """
        try:
            if not metric_values:
                return {
                    "success": True,
                    "legend": None,
                    "message": "No metric values provided"
                }

            values = list(metric_values.values())
            min_val, max_val = min(values), max(values)

            # Create legend entries
            legend_steps = 5
            legend_values = []
            for i in range(legend_steps):
                val = min_val + (max_val - min_val) * (i / (legend_steps - 1))
                legend_values.append(val)

            colors = generate_color_scale(legend_values, color_scheme)
            sizes = calculate_node_sizes(legend_values, tuple(size_range))

            legend_entries = []
            for i, val in enumerate(legend_values):
                legend_entries.append({
                    "value": round(val, 4),
                    "color": colors[i],
                    "size": round(sizes[i], 1)
                })

            return {
                "success": True,
                "legend": {
                    "entries": legend_entries,
                    "min_value": min_val,
                    "max_value": max_val,
                    "color_scheme": color_scheme,
                    "size_range": size_range
                }
            }

        except Exception as e:
            error_msg = f"Failed to create legend data: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
