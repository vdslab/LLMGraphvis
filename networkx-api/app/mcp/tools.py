from typing import List, Optional
from app.core.mcp import mcp

from app.core import database
from common import models

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
            layout.calculate_layout(final_network_id, "forceatlas2", db)

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
        layout.calculate_layout(network_id, layout_name, db)
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
            layout.calculate_layout(network_id, layout_name, db)

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
def create_subgraph_from_nodes(
    network_id: int,
    node_ids: List[str],
    description: str = "Custom subgraph",
    preserve_layout: bool = False
) -> dict:
    """
    Creates a NEW subgraph network from a list of node IDs.
    Returns schema with new_network_id.
    """
    db = database.SessionLocal()
    try:
        from app.logic import subgraph
        # Correct argument mapping:
        # source_network_id, node_ids, db, suffix, preserve_layout, description
        result = subgraph.create_subgraph_from_nodes(
            source_network_id=network_id,
            node_ids=node_ids,
            db=db,
            suffix="Subgraph",
            preserve_layout=preserve_layout,
            description=description
        )
        return {
            "new_network_id": result["new_network_id"],
            "content": f"Subgraph created (ID: {result['new_network_id']}) with {len(node_ids)} nodes."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def create_largest_component_subgraph(
    network_id: int, 
    preserve_layout: bool = False
) -> dict:
    """
    Extracts the largest connected component as a new subgraph.
    """
    db = database.SessionLocal()
    try:
        from app.logic import subgraph 
        
        result = subgraph.create_largest_component_subgraph(
            source_network_id=network_id,
            db=db,
            preserve_layout=preserve_layout
        )
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def create_ego_network(
    network_id: int,
    center_node_id: str,
    radius: int,
    preserve_layout: bool = False
) -> dict:
    """
    Creates an Ego Network subgraph (node + neighbors within radius).
    """
    db = database.SessionLocal()
    try:
        from app.logic import subgraph
        return subgraph.create_ego_network(
            source_network_id=network_id,
            center_node_id=center_node_id,
            radius=radius,
            db=db,
            preserve_layout=preserve_layout
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def create_path_subgraph(
    network_id: int,
    source_node_id: str,
    target_node_id: str,
    preserve_layout: bool = False
) -> dict:
    """
    Creates a subgraph containing the shortest path between two nodes.
    """
    db = database.SessionLocal()
    try:
        from app.logic import subgraph
        return subgraph.create_path_subgraph(
            source_network_id=network_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            db=db,
            preserve_layout=preserve_layout
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def create_k_core_subgraph(
    network_id: int,
    k: int,
    preserve_layout: bool = False
) -> dict:
    """
    Creates a k-core subgraph (nodes with degree >= k).
    """
    db = database.SessionLocal()
    try:
        from app.logic import subgraph
        return subgraph.create_k_core_subgraph(
            source_network_id=network_id,
            k=k,
            db=db,
            preserve_layout=preserve_layout
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def get_subgraphs(network_id: int) -> dict:
    """
    Lists all subgraphs derived from the given network.
    """
    db = database.SessionLocal()
    try:
        from app.logic import network_metadata
        subgraphs = network_metadata.get_subgraphs(db, network_id)
        return {"subgraphs": subgraphs}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def get_top_nodes(
    network_id: int, 
    metric: str, 
    k: int = 5
) -> dict:
    """
    Returns the top k nodes based on a centrality metric.
    Metric options: 'degree', 'betweenness', 'closeness', 'eigenvector', 'pagerank'.
    """
    db = database.SessionLocal()
    try:
        from app.logic import centrality
        nodes = centrality.get_top_nodes(network_id, metric, k, db)
        return {"top_nodes": nodes}
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


@mcp.tool()
def get_network_structure(
    network_id: int
) -> dict:
    """
    Returns basic structural statistics (node count, edge count, density).
    """
    db = database.SessionLocal()
    try:
        from app.logic import network_metadata
        return network_metadata.get_network_structure(db, network_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def list_node_attributes(
    network_id: int
) -> dict:
    """
    Lists available node attributes with statistics (min/max/top values).
    """
    db = database.SessionLocal()
    try:
        from app.logic import attributes
        stats = attributes.get_attribute_stats(
            network_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db
        )
        return {"attributes": stats}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def list_edge_attributes(
    network_id: int
) -> dict:
    """
    Lists available edge attributes with statistics.
    """
    db = database.SessionLocal()
    try:
        from app.logic import attributes
        stats = attributes.get_attribute_stats(
            network_id,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db
        )
        return {"attributes": stats}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def update_layout(
    network_id: int,
    layout_name: str
) -> dict:
    """
    Updates the network layout (e.g., 'forceatlas2', 'circular', 'kamada_kawai').
    Recalculates positions and refreshes the visualization.
    """
    db = database.SessionLocal()
    try:
        # Calculate new layout
        layout.calculate_layout(network_id, layout_name, db)
        
        # Build new visualization (updating state)
        # Note: We don't change color/size configs, just layout
        return visualization_builder.build_visualization(
            db, 
            network_id,
            layout_name=layout_name # Update the layout preference
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def update_node_color(
    network_id: int,
    attribute: str,
    scale_type: str = "CATEGORICAL"
) -> dict:
    """
    Updates the node coloring based on an attribute.
    scale_type options: "CATEGORICAL" (text), "LINEAR" (numbers), "RANKING" (top values).
    """
    db = database.SessionLocal()
    try:
        config = NodeColorConfig(
            attribute=attribute,
            scale_type=scale_type
        )
        return visualization_builder.build_visualization(
            db, network_id, node_color_config=config
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def update_node_size(
    network_id: int,
    attribute: str,
    min_size: float = 5.0,
    max_size: float = 20.0
) -> dict:
    """
    Updates the node sizing based on an attribute.
    """
    db = database.SessionLocal()
    try:
        config = NodeSizeConfig(
            attribute=attribute,
            min=min_size,
            max=max_size
        )
        return visualization_builder.build_visualization(
            db, network_id, node_size_config=config
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
