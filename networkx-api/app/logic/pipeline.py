from app.logic import importer, layout, visualizer
from app.core import database

# Re-implements `initialize_network` logic from `mcp_server.py`
def initialize_network_pipeline(network_id: int, graphml_data: str, db: database.SessionLocal):
    """
    Initializes a network from GraphML data: parses, saves, calculates layout, and generates initial visualization.
    """
    # 1. Parse and Save
    final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
    
    # 2. Initial Layout (ForceAtlas2)
    layout.calculate_layout(final_network_id, "forceatlas2", db)
    
    # 3. Initial Visualization
    vis_data = visualizer.generate_visualization_data(final_network_id, db)
    
    return {"network": vis_data, "network_id": final_network_id}
