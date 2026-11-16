from app.core import database
from app.logic import importer, layout, visualizer


# Re-implements `initialize_network` logic from `mcp_server.py`
def initialize_network_pipeline(
    network_id: int, graphml_data: str, db: database.SessionLocal
):
    """Initializes a network from GraphML data.

    Parses and saves it, calculates a layout, and generates the initial
    visualization.
    """
    # 1. Parse and Save
    final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)

    # 2. Initial Layout (ForceAtlas2, or spring where it would not settle)
    info = layout.calculate_initial_layout(final_network_id, db)

    # 3. Initial Visualization
    vis_data = visualizer.generate_visualization_data(
        final_network_id, db, layout_name=info["layout_name"]
    )

    return {"network": vis_data, "network_id": final_network_id}
