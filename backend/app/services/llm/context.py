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
            if attrs and isinstance(attrs, list):
                if attrs:
                    summary_lines.append(f"Available {label}:")
                    # Limit to top 15 to avoid context saturation
                    limit = 15
                    for i, attr in enumerate(attrs):
                        if i >= limit:
                            remaining = len(attrs) - limit
                            summary_lines.append(f"- ... and {remaining} more")
                            break
                        name = attr.get("name")
                        dtype = attr.get("data_type")
                        summary_lines.append(f"- {name} ({dtype})")
                else:
                    summary_lines.append(f"{label}: None")
            elif attrs and isinstance(attrs, dict) and "attributes" in attrs:
                # Fallback if structure changes
                ats = attrs["attributes"]
                if ats:
                    summary_lines.append(f"Available {label}:")
                    limit = 15
                    for i, attr in enumerate(ats):
                        if i >= limit:
                            remaining = len(ats) - limit
                            summary_lines.append(f"- ... and {remaining} more")
                            break
                        name = attr.get("name")
                        dtype = attr.get("data_type")
                        summary_lines.append(f"- {name} ({dtype})")
            
        format_attrs(node_attrs, "Node Attributes")
        format_attrs(edge_attrs, "Edge Attributes")

        return "\n".join(summary_lines)
    except Exception as e:
        logger.error(f"Error building context summary: {e}")
        return ""
