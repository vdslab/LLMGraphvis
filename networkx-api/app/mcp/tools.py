from typing import List, Optional, Dict, Any
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
def import_graphml(network_id: int, graphml_data: str) -> dict:
    """
    Imports GraphML data into the database.
    Returns: {"network_id": int}
    """
    db = database.SessionLocal()
    try:
        from app.logic import importer
        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        return {"network_id": final_network_id, "content": f"Imported network {final_network_id}"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


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
        centrality.calculate_centrality(network_id, centrality_type, db)
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
        community.calculate_community(network_id, algorithm, db)
        return f"Communities detected using {algorithm}."
    except ValueError as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def calculate_layout(network_id: int, layout_name: str) -> dict:
    """
    Calculates a graph layout and saves x, y coordinates as node attributes.
    Returns the updated visualization data.
    
    Supported Layouts:
    - "force-directed" (Default): Uses ForceAtlas2 algorithm. Best for most networks.
    - "spring": Uses Fruchterman-Reingold algorithm. Good for small graphs.
    - "forceatlas2": Explicitly ForceAtlas2. Native NetworkX implementation.
    - "kamada_kawai": Good global structure but slow O(N^2).
    - "circular": Position nodes on a circle.
    - "shell": Position nodes in concentric circles.
    - "spectral": Position nodes using the eigenvectors of the graph Laplacian.
    - "spiral": Position nodes in a spiral layout.
    - "random": Position nodes uniformly at random in the unit square.
    """
    db = database.SessionLocal()
    try:
        layout.calculate_layout(network_id, layout_name, db)
        # Return visualization to ensure the client updates immediately
        return visualization_builder.build_visualization(
            db, network_id, layout_name=layout_name
        )
    except ValueError as e:
        return {"error": str(e)}
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
    [INITIALIZER / RESET TOOL]
    Generates the network visualization. Use this tool primarily for:
    1.  **Initialization**: The first time you visualize a network.
    2.  **Full Reset**: If you want to change EVERYTHING at once (layout, color, size).
    
    **Best Practice**:
    -   For simple updates (e.g., "Change color to red"), use the specialized tools:
        -   `update_node_color`
        -   `update_node_size`
        -   `update_layout`
    -   This tool allows complex nested configurations but is harder to get right.
    
    **Persisted State**:
    -   Any config provided here (not None) is saved to the database.
    -   Any config set to None will PRESERVE the existing state from the database.
    
    Args:
        network_id: The ID of the network.
        layout_name: "forceatlas2", "circular", "kamada_kawai", etc.
        node_color_config: Complex object for coloring.
        node_size_config: Complex object for sizing.
        # ... other configs
    """
    db = database.SessionLocal()
    try:
        # 1. Update Layout if requested
        # REMOVED: Implicit calculation. Agent must call calculate_layout explicitly.
        # if layout_name:
        #     layout.calculate_layout(network_id, layout_name, db)

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
        nodes = search.search_nodes(network_id, query, limit=limit, db=db)
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
    Updates the network layout.
    
    Supported Layouts:
    - "force-directed" (Default, ForceAtlas2)
    - "spring" (Fruchterman-Reingold)
    - "circular": Position nodes on a circle.
    - "shell": Position nodes in concentric circles.
    - "spectral": Eigenvectors of graph Laplacian.
    - "spiral": Spiral layout.
    - "kamada_kawai", "random", etc.
    
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
    scale_type: str = "CATEGORICAL",
    mapping: Optional[Dict[str, str]] = None,
    default_color: Optional[str] = None,
    fixed: bool = False,
    gradient: Optional[List[str]] = None
) -> dict:
    """
     Updates the node coloring based on an attribute.
    
    **Example: Specific Value Mapping**
    To color "Austria" nodes red and all others gray:
    >>> update_node_color(
            network_id=1,
            attribute="country",          # The attribute to check
            scale_type="CATEGORICAL",
            mapping={"Austria": "red"},   # Specific mapping
            default_color="gray",         # Fallback for others
            fixed=True                    # Do not auto-generate other colors
        )
        
    Args:
        network_id: The ID of the network.
        attribute: The attribute name (e.g., 'country', 'modularity_class').
        scale_type: "CATEGORICAL" (text), "LINEAR" (numbers), "RANKING" (top k).
        mapping: Dictionary for explicit value->color pairs (e.g., {"Japanese": "red"}).
        default_color: Color for nodes that don't match the mapping or are null. Defaults to Gray (#d3d3d3).
        fixed: If True, STRICTLY uses the mapping + default. If False, auto-assigns colors to missing values.
        gradient: List of colors for LINEAR scale (e.g. ["#start", "#end"] or ["#start", "#mid", "#end"]).
    """
    db = database.SessionLocal()
    try:
        # Default to Gray for null/mismatched values if not specified
        if not default_color:
            default_color = "#d3d3d3"

        config = NodeColorConfig(
            attribute=attribute,
            scale_type=scale_type,
            color_map=mapping,
            default_color=default_color,
            fixed_mapping=fixed,
            gradient=gradient
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


@mcp.tool()
def get_node_details(
    network_id: int,
    node_id: str
) -> dict:
    """
    Returns full details for a specific node, including all attributes.
    """
    db = database.SessionLocal()
    try:
        from app.logic import search
        details = search.get_node_details(network_id, node_id, db)
        if not details:
            return {"error": f"Node '{node_id}' not found in network {network_id}."}
        return details
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def filter_nodes(
    network_id: int,
    attribute_name: str,
    value: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    limit: int = 100
) -> dict:
    """
    Lists nodes that match a specific attribute condition.
    Does NOT create a new network, just returns a list of matching nodes (id, label).
    
    Args:
        network_id: ID of the network.
        attribute_name: Name of the attribute to filter by.
        value: Exact string match for text attributes OR exact float match for numeric.
        min_value: Minimum value for numeric range.
        max_value: Maximum value for numeric range.
        limit: Max number of nodes to return (default 100).
    """
    db = database.SessionLocal()
    try:
        from app.logic import filter as filter_logic
        from app.schemas.filter import AttributeCondition, Range

        # Construct condition
        condition = AttributeCondition(attribute_name=attribute_name)
        
        if value is not None:
             # Try to parse as float if it looks like a number, otherwise keep as string
            try:
                condition.categories = [float(value)]
            except ValueError:
                condition.categories = [value]
        
        if min_value is not None or max_value is not None:
            condition.ranges = [Range(min=min_value, max=max_value)]
            
        nodes = filter_logic.get_nodes_by_filter(network_id, [condition], db)
        
        # Limit results
        truncated = False
        if len(nodes) > limit:
            nodes = nodes[:limit]
            truncated = True
            
        return {
            "count": len(nodes),
            "truncated": truncated,
            "nodes": nodes
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
