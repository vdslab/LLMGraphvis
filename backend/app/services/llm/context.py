from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from . import mcp_client

logger = get_logger(__name__)


async def _fetch_network_resources(
    network_id: int,
) -> Tuple[Any, Any, Any, Any]:
    """Fetch the network's metadata, structure and node/edge attributes in one session."""
    async with mcp_client.session_scope() as session:
        metadata = await mcp_client.get_resource(
            f"network://{network_id}/metadata", session=session
        )
        structure = await mcp_client.get_resource(
            f"network://{network_id}/structure", session=session
        )
        node_attrs = await mcp_client.get_resource(
            f"network://{network_id}/attributes/nodes", session=session
        )
        edge_attrs = await mcp_client.get_resource(
            f"network://{network_id}/attributes/edges", session=session
        )
    return metadata, structure, node_attrs, edge_attrs


def _normalize_attrs(attrs: Any) -> List[Dict[str, Any]]:
    """Normalize an attributes resource (list, or dict wrapping a list) to a list."""
    if isinstance(attrs, dict) and "attributes" in attrs:
        return attrs["attributes"] or []
    if isinstance(attrs, list):
        return attrs
    return []


def _format_attr_stats(dtype: Optional[str], stats: Optional[Dict[str, Any]]) -> str:
    """Render an attribute's value range (floats) or top values (strings) as a suffix."""
    if not stats:
        return ""
    if dtype == "float" and "min" in stats and "max" in stats:
        return f" [min: {stats['min']:.2f}, max: {stats['max']:.2f}]"
    if dtype == "string" and "top_values" in stats:
        top_vals = stats["top_values"]
        # Only show up to 5 values to avoid overwhelming the reader/context.
        display_vals = top_vals[:5]
        vals_str = ", ".join([f"'{v}'" for v in display_vals])
        if len(top_vals) > 5:
            vals_str += ", ..."
        return f" [values: {vals_str}]"
    return ""


async def build_context_summary(network_id: int) -> str:
    """Fetches network stats and attributes to build a context summary string.

    This runs on every turn (via the backend, not an LLM tool call) and is
    appended to the system prompt so the agent always knows the network's
    contents regardless of the user's message.
    """
    try:
        metadata, structure, node_attrs, edge_attrs = await _fetch_network_resources(
            network_id
        )

        summary_lines = ["[Current Network Context]"]
        summary_lines.append(f"Network ID: {network_id}")

        if isinstance(metadata, dict):
            name = metadata.get("name")
            description = metadata.get("description")
            if name:
                summary_lines.append(f"Name: {name}")
            if description:
                summary_lines.append(f"Description: {description}")

        if structure:
            n_count = structure.get("node_count", "?")
            e_count = structure.get("edge_count", "?")
            summary_lines.append(f"Stats: {n_count} Nodes, {e_count} Edges")

        def format_attrs(attrs: Any, label: str) -> None:
            attrs_list = _normalize_attrs(attrs)
            if not attrs_list:
                summary_lines.append(f"{label}: None")
                return
            summary_lines.append(f"Available {label}:")
            limit = 15
            for i, attr in enumerate(attrs_list):
                if i >= limit:
                    remaining = len(attrs_list) - limit
                    summary_lines.append(f"- ... and {remaining} more")
                    break
                name = attr.get("name")
                dtype = attr.get("data_type")
                stats_str = _format_attr_stats(dtype, attr.get("stats"))
                summary_lines.append(f"- {name} ({dtype}){stats_str}")

        format_attrs(node_attrs, "Node Attributes")
        format_attrs(edge_attrs, "Edge Attributes")

        return "\n".join(summary_lines)
    except Exception as e:
        logger.error(f"Error building context summary: {e}")
        return ""


async def build_data_overview(network_id: int) -> str:
    """Build a user-facing Markdown overview of the uploaded network's contents.

    Used at upload time to show what the data contains before the user sends
    their first message. Like build_context_summary, this reads MCP resources
    directly from the backend — it does not rely on the LLM calling any tool.
    """
    try:
        metadata, structure, node_attrs, edge_attrs = await _fetch_network_resources(
            network_id
        )

        lines: List[str] = ["**Uploaded network overview**", ""]

        if isinstance(metadata, dict):
            name = metadata.get("name")
            description = metadata.get("description")
            if name:
                lines.append(f"- **Name:** {name}")
            if description:
                lines.append(f"- **Description:** {description}")

        if structure:
            n_count = structure.get("node_count", "?")
            e_count = structure.get("edge_count", "?")
            lines.append(f"- **Size:** {n_count} nodes, {e_count} edges")

        def format_attrs_md(attrs: Any, label: str) -> None:
            attrs_list = _normalize_attrs(attrs)
            lines.append("")
            if not attrs_list:
                lines.append(f"**{label}:** none")
                return
            lines.append(f"**{label}:**")
            limit = 15
            for i, attr in enumerate(attrs_list):
                if i >= limit:
                    lines.append(f"- ... and {len(attrs_list) - limit} more")
                    break
                name = attr.get("name")
                dtype = attr.get("data_type")
                stats_str = _format_attr_stats(dtype, attr.get("stats"))
                lines.append(f"- `{name}` ({dtype}){stats_str}")

        format_attrs_md(node_attrs, "Node attributes")
        format_attrs_md(edge_attrs, "Edge attributes")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error building data overview: {e}")
        return ""
