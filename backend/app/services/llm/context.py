import json
from typing import Optional, List, Dict, Any

from app.core.logging import get_logger
from . import mcp_client

logger = get_logger(__name__)

async def build_context_summary(network_id: int) -> str:
    """Fetches network stats and attributes to build a context summary string."""
    try:
        # Fetch resources using a single session to reduce overhead
        async with mcp_client.session_scope() as session:
            structure = await mcp_client.get_resource(
                f"network://{network_id}/structure", session=session
            )
            node_attrs = await mcp_client.get_resource(
                f"network://{network_id}/attributes/nodes", session=session
            )
            edge_attrs = await mcp_client.get_resource(
                f"network://{network_id}/attributes/edges", session=session
            )

        summary_lines = ["[Current Network Context]"]
        summary_lines.append(f"Network ID: {network_id}")

        if structure:
            n_count = structure.get("node_count", "?")
            e_count = structure.get("edge_count", "?")
            summary_lines.append(f"Stats: {n_count} Nodes, {e_count} Edges")

        # Helper to format attributes
        def format_attrs(attrs, label):
            # Normalization: in some cases attrs might be wrapped in a dict
            if isinstance(attrs, dict) and "attributes" in attrs:
                attrs_list = attrs["attributes"]
            elif isinstance(attrs, list):
                attrs_list = attrs
            else:
                attrs_list = []

            if attrs_list:
                summary_lines.append(f"Available {label}:")
                limit = 15
                for i, attr in enumerate(attrs_list):
                    if i >= limit:
                        remaining = len(attrs_list) - limit
                        summary_lines.append(f"- ... and {remaining} more")
                        break
                    
                    name = attr.get("name")
                    dtype = attr.get("data_type")
                    stats = attr.get("stats")
                    
                    stats_str = ""
                    if stats:
                        if dtype == "float" and "min" in stats and "max" in stats:
                            stats_str = f" [min: {stats['min']:.2f}, max: {stats['max']:.2f}]"
                        elif dtype == "string" and "top_values" in stats:
                            top_vals = stats["top_values"]
                            # Only show up to 5 values in the summary to avoid overwhelming the context
                            display_vals = top_vals[:5]
                            vals_str = ", ".join([f"'{v}'" for v in display_vals])
                            if len(top_vals) > 5:
                                vals_str += ", ..."
                            stats_str = f" [values: {vals_str}]"
                            
                    summary_lines.append(f"- {name} ({dtype}){stats_str}")
            else:
                summary_lines.append(f"{label}: None")
            
        format_attrs(node_attrs, "Node Attributes")
        format_attrs(edge_attrs, "Edge Attributes")

        return "\n".join(summary_lines)
    except Exception as e:
        logger.error(f"Error building context summary: {e}")
        return ""
