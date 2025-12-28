from typing import List, Optional, Dict, Any, Annotated
from pydantic import Field
from app.core.mcp import mcp

from app.core import database
from common import models
import logging
import traceback

logger = logging.getLogger("app.mcp.tools")

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
def import_graphml(
    network_id: Annotated[int, Field(description="The ID of the network record in the database.")],
    graphml_data: Annotated[str, Field(description="The **raw XML string content** of the GraphML file (not a file path).")]
) -> dict:
    """
    Imports GraphML data into the database.
    
    Returns:
        dict: {"network_id": int, "content": str}
    """
    db = database.SessionLocal()
    try:
        from app.logic import importer
        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        return {"network_id": final_network_id, "content": f"Imported network {final_network_id}"}
    except Exception as e:
        logger.error(f"import_graphml failed: {e}")
        logger.error(traceback.format_exc())
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def initialize_network(
    network_id: Annotated[int, Field(description="The ID of the network record in the database.")],
    graphml_data: Annotated[str, Field(description="The **raw XML string content** of the GraphML file (not a file path).")]
) -> dict:
    """
    Initializes a network from GraphML data.
    This tool parses the GraphML, saves it to the DB, calculates a default layout,
    and returns the initial visualization data.

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    db = database.SessionLocal()
    try:
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
             logger.error(f"initialize_network logic failed: {e}")
             logger.error(traceback.format_exc())
             return {"content": f"Import failed: {type(e).__name__}: {str(e)}"}
    except Exception as e:
        logger.error(f"initialize_network critical failure: {e}")
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def calculate_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    centrality_type: Annotated[str, Field(description="The type of centrality to calculate. Valid values: 'degree', 'betweenness', 'closeness', 'eigenvector', 'pagerank'.")]
) -> str:
    """
    Calculates specific centrality for the network and saves it as a node attribute.
            
    Returns:
        str: Status message.
    """
    db = database.SessionLocal()
    try:
        centrality.calculate_centrality(network_id, centrality_type, db)
        return f"{centrality_type} centrality calculated."
    except Exception as e:
        logger.error(f"calculate_centrality failed: {e}")
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def calculate_community(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    algorithm: Annotated[str, Field(description="The algorithm to use for community detection. Valid values: 'louvain', 'greedy_modularity', 'label_propagation'. Default is 'louvain'.")] = "louvain"
) -> str:
    """
    Detects communities in the network and saves them as a node attribute ('community').
            
    Returns:
        str: Status message.
    """
    db = database.SessionLocal()
    try:
        community.calculate_community(network_id, algorithm, db)
        return f"Communities detected using {algorithm}."
    except Exception as e:
        logger.error(f"calculate_community failed: {e}")
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def calculate_layout(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    layout_name: Annotated[str, Field(description="The name of the layout algorithm to use. Supported Layouts: 'forceatlas2' (Default), 'spring', 'kamada_kawai', 'circular', 'shell', 'spectral', 'spiral', 'random'.")]
) -> dict:
    """
    Calculates a graph layout and saves x, y coordinates as node attributes.
    Returns the updated visualization data (nodes with new x,y).
    
    Args:
        network_id: The ID of the network.
        layout_name: The name of the layout algorithm to use.
            Supported Layouts:
            - "forceatlas2" (Default): Best for most networks (force-directed).
            - "spring": Fruchterman-Reingold algorithm. Good for small graphs.
            - "kamada_kawai": Good global structure but slow (O(N^2)).
            - "circular": Position nodes on a circle.
            - "shell": Position nodes in concentric circles.
            - "spectral": Position nodes using the eigenvectors of the graph Laplacian.
            - "spiral": Position nodes in a spiral layout.
            - "random": Position nodes uniformly at random.
            
    Returns:
        dict: The updated visualization data (same format as generate_visualization).
    """
    db = database.SessionLocal()
    try:
        layout.calculate_layout(network_id, layout_name, db)
        # Return visualization to ensure the client updates immediately
        return visualization_builder.build_visualization(
            db, network_id, layout_name=layout_name
        )
    except Exception as e:
        logger.error(f"calculate_layout failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def generate_visualization(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    layout_name: Annotated[Optional[str], Field(description="Layout algorithm to use (e.g., 'forceatlas2', 'circular'). If None, preserves current.")] = None,
    node_color_config: Annotated[Optional[NodeColorConfig], Field(description="Complex object for node coloring configuration.")] = None,
    node_size_config: Annotated[Optional[NodeSizeConfig], Field(description="Complex object for node sizing configuration.")] = None,
    edge_width_config: Annotated[Optional[EdgeWidthConfig], Field(description="Complex object for edge width configuration.")] = None,
    edge_color_config: Annotated[Optional[EdgeColorConfig], Field(description="Complex object for edge color configuration.")] = None,
    context_config: Annotated[Optional[dict], Field(description="Configuration for context view (visual style of non-focused elements).")] = None,
    focus_config: Annotated[Optional[dict], Field(description="Configuration for focus view (visual style of focused elements).")] = None,
    node_label_config: Annotated[Optional[NodeLabelConfig], Field(description="Configuration for node labels.")] = None,
    custom_node_colors: Annotated[Optional[list], Field(description="List of specific {'node_id': 'id', 'color': 'hex'} overrides.")] = None,
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
        
    Returns:
        dict: The complete visualization data {"nodes": [...], "links": [...], "legend": ...}
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
    except Exception as e:
        logger.error(f"generate_visualization failed: {e}")
        logger.error(traceback.format_exc())
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def create_subgraph_from_nodes(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    node_ids: Annotated[List[str], Field(description="List of node IDs (strings) to include in the subgraph.")],
    description: Annotated[str, Field(description="Description of the subgraph (e.g., 'Neighbors of Node A').")] = "Custom subgraph",
    preserve_layout: Annotated[bool, Field(description="If True, copies the x,y coordinates from the source network.")] = False
) -> dict:
    """
    Creates a NEW subgraph network from a list of specific node IDs.
        
    Returns:
        dict: {"new_network_id": int, "content": str}
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
        logger.error(f"create_subgraph_from_nodes failed: {e}")
        logger.error(traceback.format_exc())
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def create_largest_component_subgraph(
    network_id: Annotated[int, Field(description="The ID of the source network.")], 
    preserve_layout: Annotated[bool, Field(description="If True, copies the x,y coordinates from the source network.")] = False
) -> dict:
    """
    Extracts the largest connected component from the network as a new subgraph.
        
    Returns:
        dict: {"new_network_id": int, "content": str}
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
        logger.error(f"create_largest_component_subgraph failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def create_ego_network(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    center_node_id: Annotated[str, Field(description="The ID of the central node.")],
    radius: Annotated[int, Field(description="The radius of the ego network (1 = direct neighbors).")],
    preserve_layout: Annotated[bool, Field(description="If True, copies the x,y coordinates from the source network.")] = False
) -> dict:
    """
    Creates an Ego Network subgraph (a central node and its neighbors within a radius).
        
    Returns:
        dict: {"new_network_id": int, "content": str}
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
        logger.error(f"create_ego_network failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def create_path_subgraph(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    source_node_id: Annotated[str, Field(description="The start node ID.")],
    target_node_id: Annotated[str, Field(description="The end node ID.")],
    preserve_layout: Annotated[bool, Field(description="If True, copies the x,y coordinates from the source network.")] = False
) -> dict:
    """
    Creates a subgraph containing the shortest path between two specific nodes.
        
    Returns:
        dict: {"new_network_id": int, "content": str}
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
        logger.error(f"create_path_subgraph failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def create_k_core_subgraph(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    k: Annotated[int, Field(description="The minimum degree for nodes to include.")],
    preserve_layout: Annotated[bool, Field(description="If True, copies the x,y coordinates from the source network.")] = False
) -> dict:
    """
    Creates a k-core subgraph (containing only nodes with degree >= k).
        
    Returns:
        dict: {"new_network_id": int, "content": str}
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
        logger.error(f"create_k_core_subgraph failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def get_subgraphs(
    network_id: Annotated[int, Field(description="The ID of the parent network.")]
) -> dict:
    """
    Lists all subgraphs derived from the given network.
        
    Returns:
        dict: {"subgraphs": [{"id": int, "name": str, ...}]}
    """
    db = database.SessionLocal()
    try:
        from app.logic import network_metadata
        subgraphs = network_metadata.get_subgraphs(db, network_id)
        return {"subgraphs": subgraphs}
    except Exception as e:
        logger.error(f"get_subgraphs failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def get_top_nodes(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    metric: Annotated[str, Field(description="Centrality metric to use. Valid values: 'degree', 'betweenness', 'closeness', 'eigenvector', 'pagerank'.")],
    k: Annotated[int, Field(description="Number of top nodes to return.")] = 10
) -> dict:
    """
    Returns the top k nodes based on a centrality metric.
        
    Returns:
        dict: {"nodes": [{"id": str, "score": float}, ...]}
    """
    db = database.SessionLocal()
    try:
        from app.logic import centrality
        nodes = centrality.get_top_nodes(network_id, metric, k, db)
        return {"top_nodes": nodes}
    except Exception as e:
        logger.error(f"get_top_nodes failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def search_nodes(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    query: Annotated[str, Field(description="The search string (matches partial node IDs).")],
    limit: Annotated[int, Field(description="Max results to return.")] = 10
) -> str:
    """
    Search for nodes by ID or attributes.
        
    Returns:
        str: Description of found nodes.
    """
    db = database.SessionLocal()
    try:
        nodes = search.search_nodes(network_id, query, limit=limit, db=db)
        return f"Found {len(nodes)} nodes: {nodes}"
    except Exception as e:
        logger.error(f"search_nodes failed: {e}")
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def export_network(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Exports the network as a GraphML string.
        
    Returns:
        str: The GraphML content string.
    """
    db = database.SessionLocal()
    try:
        from app.logic import export
        return export.export_to_graphml(db, network_id)
    except Exception as e:
        logger.error(f"export_network failed: {e}")
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def get_visualization_state(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Returns the current visualization configuration (color mapping, sizing, layout, etc.).
    By reading this, you can understand how the network is currently visualized.
        
    Returns:
        dict: A dictionary containing 'layout_name', 'node_size', 'node_color', etc.
    """
    db = database.SessionLocal()
    try:
        return visualization_builder.get_current_visualization(db, network_id)
    except Exception as e:
        logger.error(f"get_visualization_state failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def get_network_structure(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Returns basic structural statistics (node count, edge count, density).
    """
    db = database.SessionLocal()
    try:
        from app.logic import network_metadata
        return network_metadata.get_network_structure(db, network_id)
    except Exception as e:
        logger.error(f"get_network_structure failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def list_node_attributes(
    network_id: Annotated[int, Field(description="The ID of the network.")]
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
        logger.error(f"list_node_attributes failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def list_edge_attributes(
    network_id: Annotated[int, Field(description="The ID of the network.")]
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
        logger.error(f"list_edge_attributes failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def update_layout(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    layout_name: Annotated[str, Field(description="The layout algorithm. Supported: 'forceatlas2', 'spring', etc.")]
) -> dict:
    """
    Updates the network layout.
        
    Returns:
        dict: Updated visualization data.
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
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="The attribute name (e.g., 'country', 'modularity_class') to use for coloring.")],
    scale_type: Annotated[str, Field(description="How to map values to colors. 'CATEGORICAL' (distinct), 'LINEAR' (gradient), 'RANKING' (top-k).")] = "CATEGORICAL",
    mapping: Annotated[Optional[Dict[str, str]], Field(description="Optional dictionary for explicit value->color pairs. e.g. {'Japan': 'red'}.")] = None,
    default_color: Annotated[Optional[str], Field(description="Fallback color for nodes that don't match mapping or are null. Default: '#d3d3d3'.")] = None,
    fixed: Annotated[bool, Field(description="If True, strictly uses mapping+default. If False (default), auto-generates types.")] = False,
    gradient: Annotated[Optional[List[str]], Field(description="List of colors for LINEAR scale (e.g. ['#ffffff', '#ff0000']).")] = None
) -> dict:
    """
    Updates the node coloring based on an attribute.
    
    Returns:
        dict: Updated visualization data.
        
    Example:
    To color "Austria" nodes red and all others gray:
    >>> update_node_color(
            network_id=1,
            attribute="country",
            scale_type="CATEGORICAL",
            mapping={"Austria": "red"},
            default_color="#d3d3d3",
            fixed=True
        )
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
        logger.error(f"update_node_color failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def update_node_size(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="The attribute name (number) to use for sizing.")],
    min_size: Annotated[float, Field(description="Node radius for the minimum attribute value.")] = 5.0,
    max_size: Annotated[float, Field(description="Node radius for the maximum attribute value.")] = 20.0
) -> dict:
    """
    Updates the node sizing based on an attribute.
    
    Returns:
        dict: Updated visualization data.
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
        logger.error(f"update_node_size failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}

    finally:
        db.close()


@mcp.tool()
def get_node_details(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_id: Annotated[str, Field(description="The ID of the node to retrieve details for.")]
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
        logger.error(f"get_node_details failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def filter_nodes(
    network_id: Annotated[int, Field(description="ID of the network.")],
    attribute_name: Annotated[str, Field(description="Name of the attribute to filter by.")],
    value: Annotated[Optional[str], Field(description="Exact string match for text attributes OR exact float match for numeric.")] = None,
    min_value: Annotated[Optional[float], Field(description="Minimum value for numeric range.")] = None,
    max_value: Annotated[Optional[float], Field(description="Maximum value for numeric range.")] = None,
    limit: Annotated[int, Field(description="Max number of nodes to return.")] = 100
) -> dict:
    """
    Lists nodes that match a specific attribute condition.
    Does NOT create a new network, just returns a list of matching nodes (id, label).
    
    Returns:
        dict: {"count": int, "truncated": bool, "nodes": List[dict]}
        
    WARNING:
    - Use this tool ONLY for retrieving information (e.g., "List Austrian composers").
    - Do NOT use this tool to get IDs for creating a subgraph. Use `create_subgraph_by_filter` instead,
      which handles the filtering server-side and avoids Context Window limits.
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
        logger.error(f"filter_nodes failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def create_subgraph_by_filter(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    conditions: Annotated[List[Dict[str, Any]], Field(description="List of conditions. Schema: [{'attribute': 'Name', 'categories': ['A', 'B'], 'ranges': [{'min': 10, 'max': 20}]}]")],
    preserve_layout: Annotated[bool, Field(description="If True, keeps x,y positions from source.")] = False,
    description: Annotated[Optional[str], Field(description="Description of the subgraph.")] = None
) -> dict:
    """
    Creates a NEW subgraph by filtering nodes based on multiple attribute conditions.
    
    Logic:
    - Multiple conditions in the `conditions` list are combined with **AND**.
    - Within a single condition, values in `categories` and `ranges` are combined with **OR**.

    Args:
        network_id: The ID of the network.
        conditions: List of filter conditions. Each dictionary MUST follow this schema:
            ```json
            {
               "attribute": "Attribute Name",
               "categories": ["Category1", "Category2"],  // Exact matches (OR logic)
               "ranges": [{"min": 10, "max": 20}, {"min": 50}] // Numeric ranges (OR logic)
            }
            ```
        preserve_layout: If True, keeps x,y positions from source.
        description: Description of the subgraph.
        
    Returns:
        dict: {"new_network_id": int, "content": str}
    """
    db = database.SessionLocal()
    try:
        from app.logic import filter as filter_logic
        from app.schemas.filter import AttributeCondition, Range

        parsed_conditions = []
        for cond_dict in conditions:
            # 1. Attribute Name
            attr_name = cond_dict.get("attribute")
            if not attr_name:
                continue # Skip invalid
            
            # 2. Categories
            categories = cond_dict.get("categories")
            
            # 3. Ranges
            ranges_data = cond_dict.get("ranges")
            parsed_ranges = None
            if ranges_data:
                parsed_ranges = []
                for r in ranges_data:
                    parsed_ranges.append(Range(min=r.get("min"), max=r.get("max")))

            parsed_conditions.append(AttributeCondition(
                attribute_name=attr_name,
                categories=categories,
                ranges=parsed_ranges
            ))

        if not parsed_conditions:
            return {"error": "No valid conditions provided."}

        if not description:
            description = "Custom filtered subgraph"

        result = filter_logic.create_subgraph_by_filter(
            network_id=network_id,
            conditions=parsed_conditions,
            suffix="Filtered",
            db=db,
            preserve_layout=preserve_layout,
            description=description
        )
        
        return {
            "new_network_id": result["new_network_id"],
            "content": f"Subgraph created (ID: {result['new_network_id']}) based on filters."
        }
            
    except Exception as e:
        logger.error(f"create_subgraph_by_filter failed: {e}")
        logger.error(traceback.format_exc())
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()
