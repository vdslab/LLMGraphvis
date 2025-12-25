from typing import List, Optional
from app.core.mcp import mcp
from app.core import database

from app.logic import (
    centrality,
    community,
    layout,
    network_metadata,
    search,
    subgraph,
    visualization_builder,
    importer
)
from app.schemas.visualization import (
    EdgeColorConfig,
    EdgeWidthConfig,
    NodeColorConfig,
    NodeLabelConfig,
    NodeSizeConfig,
)

# --- Tools ---

@mcp.tool()
def initialize_network(network_id: int, graphml_data: str) -> dict:
    """
    Initializes a network from GraphML data.

    Args:
        network_id: The ID of the network record in the database.
        graphml_data: The **raw XML string content** of the GraphML file (not a file path).
    """
    db = database.SessionLocal()
    try:
        import logging
        logger = logging.getLogger("app.mcp.tools")
        logger.info(f"DEBUG: initialize_network args types: network_id={type(network_id)}, graphml_data={type(graphml_data)}, db={type(db)}")
        
        try:
            # Importer handles parsing and collision logic
            logger.info("Calling importer.parse_and_save_graphml...")
            final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
            logger.info(f"Importer returned: {final_network_id}")
            
            # 3. Calculate Default Layout
            layout.calculate_layout(db, final_network_id, "forceatlas2")

            # 4. Generate Visualization
            vis_data = visualization_builder.build_visualization(db, final_network_id)
            
            return {
                "network_id": final_network_id,
                "network": vis_data,
                "content": f"Network initialized (ID: {final_network_id}) with {len(vis_data['nodes'])} nodes."
            }
        except Exception as e:
             return {"content": f"Import failed: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def calculate_centrality(network_id: int, centrality_type: str) -> str:
    """Calculates specific centrality for the network."""
    db = database.SessionLocal()
    try:
        centrality.calculate_centrality(db, network_id, centrality_type)
        return f"{centrality_type} centrality calculated."
    except ValueError as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def calculate_community(network_id: int, algorithm: str = "louvain") -> str:
    """Detects communities in the network."""
    db = database.SessionLocal()
    try:
        community.detect_communities(db, network_id, algorithm)
        return f"Communities detected using {algorithm}."
    except ValueError as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def calculate_layout(network_id: int, layout_name: str) -> str:
    """Calculates a graph layout and saves x, y coordinates as node attributes."""
    db = database.SessionLocal()
    try:
        layout.calculate_layout(db, network_id, layout_name)
        return f"Layout {layout_name} calculated."
    except ValueError as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def generate_visualization(
    network_id: int,
    layout_name: Optional[str] = None,
    node_color_config: Optional[NodeColorConfig] = None,
    node_size_config: Optional[NodeSizeConfig] = None,
    edge_width_config: Optional[EdgeWidthConfig] = None,
    edge_color_config: Optional[EdgeColorConfig] = None,
    context_config: Optional[dict] = None,
    focus_config: Optional[dict] = None,
    node_label_config: Optional[NodeLabelConfig] = None,
    custom_node_colors: Optional[list] = None,
) -> dict:
    """
    Generates AND UPDATES the visualization state.
    Call this ONLY when you want to CHANGE how the network looks.
    """
    db = database.SessionLocal()
    try:
        # 1. Update Layout if requested
        if layout_name:
            layout.calculate_layout(db, network_id, layout_name)

        # 2. Build Visualization
        vis_data = visualization_builder.build_visualization(
            db,
            network_id,
            node_color_config,
            node_size_config,
            edge_width_config,
            edge_color_config,
            context_config,
            focus_config,  
            node_label_config, 
            custom_node_colors
        )
        return vis_data
    finally:
        db.close()


@mcp.tool()
def create_subgraph(
    network_id: int,
    parent_network_id: int,
    node_ids: List[str],
    description: str
) -> dict:
    """
    Creates a NEW subgraph network from a list of node IDs.
    Returns schema with new_network_id.
    """
    db = database.SessionLocal()
    try:
        new_id = subgraph.create_subgraph_from_nodes(
            db, parent_network_id, node_ids, description, network_id
        )
        return {
            "new_network_id": new_id,
            "content": f"Subgraph created (ID: {new_id}) with {len(node_ids)} nodes."
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def extract_largest_component(
    network_id: int, 
    parent_network_id: int
) -> dict:
    """
    Extracts the largest connected component as a new subgraph.
    """
    db = database.SessionLocal()
    try:
        from app.logic import subgraph 
        
        result = subgraph.extract_largest_component(db, parent_network_id, network_id)
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def search_nodes(
    network_id: int,
    query: str,
    limit: int = 10
) -> str:
    """
    Search for nodes by ID or attributes.
    """
    db = database.SessionLocal()
    try:
        nodes = search.search_nodes(db, network_id, query, limit)
        return f"Found {len(nodes)} nodes: {nodes}"
    finally:
        db.close()


@mcp.tool()
def export_network(network_id: int) -> str:
    """
    Exports the network as a GraphML string.
    """
    db = database.SessionLocal()
    try:
        from app.logic import export
        return export.export_to_graphml(db, network_id)
    finally:
        db.close()


@mcp.tool()
def get_visualization_state(network_id: int) -> dict:
    """
    Returns the current visualization configuration (color mapping, sizing, etc.).
    """
    db = database.SessionLocal()
    try:
        return visualization_builder.get_current_visualization(db, network_id)
    finally:
        db.close()
