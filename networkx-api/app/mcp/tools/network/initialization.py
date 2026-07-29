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
    Does NOT generate a layout or visualization.
    To get a usable visualization afterward, call `layout_forceatlas2` then `visualization_apply_layout`.

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
    Initializes a network from GraphML data with a default ForceAtlas2 layout.
    This is the recommended entry point: parses the GraphML, saves it to the DB,
    calculates the default layout, and returns the initial visualization.

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
