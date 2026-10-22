from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging
import traceback

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def network_import_graphml(
    network_id: Annotated[int, Field(description="The ID of the network record in the database.")],
    graphml_data: Annotated[str, Field(description="The **raw XML string content** of the GraphML file (not a file path).")]
) -> dict:
    """
    Parses raw GraphML content and saves it to the database for the given network ID.

    This is the import primitive: it does NOT compute a layout or render anything.
    For a usable visualization, follow it with `layout_forceatlas2` (or any other
    `layout_*` tool) and then `visualization_generate`. Keeping the three steps separate
    lets you choose the layout and its parameters instead of taking a fixed default.

    Returns:
        dict: {"network_id": int, "content": str}
    """
    with get_db_context() as db:
        from app.logic import importer
        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        return {"network_id": final_network_id, "content": f"Imported network {final_network_id}"}


@mcp.tool()
@handle_tool_errors
def network_initialize(
    network_id: Annotated[int, Field(description="The ID of the network record in the database.")],
    graphml_data: Annotated[str, Field(description="The **raw XML string content** of the GraphML file (not a file path).")]
) -> dict:
    """
    DEPRECATED — prefer the three explicit steps below.

    Bundles three separate concerns into one call: parses and saves the GraphML, computes a
    hardcoded ForceAtlas2 layout with no way to pass parameters, and renders. Because the
    layout is fixed, a caller who wants any other layout pays for ForceAtlas2 first and
    then recomputes.

    Use instead:
      1. `network_import_graphml(network_id, graphml_data)`
      2. any `layout_*` tool, with whatever parameters suit the graph
      3. `visualization_generate(network_id)`

    Retained so existing callers keep working. The application's own upload pipeline
    already uses the three-step form.

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        logger.info(f"network_initialize: network_id={network_id}, graphml_data type={type(graphml_data)}")

        from app.logic import importer, layout, visualization_builder

        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        layout.calculate_layout(final_network_id, "forceatlas2", db)
        vis_data = visualization_builder.build_visualization(db, final_network_id)

        return {
            "network_id": final_network_id,
            "network": vis_data,
            "content": f"Network initialized (ID: {final_network_id}) with {len(vis_data['nodes'])} nodes."
        }
