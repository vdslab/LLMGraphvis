import json
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from app import models
from app.core import database
from app.logic import (
    attributes,
    centrality,
    layout,
    network_service,
    pipeline,
    prompts,
    search,
    subgraph,
    visualizer,
)

# Initialize FastMCP Server
mcp = FastMCP("NetworkX Agent", host="0.0.0.0")


def get_db_session():
    """Helper to get a database session."""
    return database.SessionLocal()


@mcp.tool()
def update_network_metadata(
    network_id: int, description: str = None, name: str = None
) -> str:
    """Updates the network's name or description."""
    db = get_db_session()
    try:
        msg = network_service.update_network_metadata(db, network_id, description, name)
        return msg
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.resource("network://{network_id}/metadata")
def get_network_metadata(network_id: int) -> str:
    """Returns network metadata (name, description, created_at) as JSON."""
    db = get_db_session()
    try:
        metadata = network_service.get_network_metadata(db, network_id)
        return json.dumps(metadata)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/nodes")
def get_node_attributes(network_id: int) -> str:
    """Lists available node attributes with metadata (type, min/max, distinct values)."""
    db = get_db_session()
    try:
        stats = attributes.get_attribute_stats(
            network_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db,
        )
        return json.dumps(stats)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/nodes/{attribute_name}")
def get_node_attribute_details(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific node attribute."""
    db = get_db_session()
    try:
        stats = attributes.get_specific_attribute_stats(
            network_id,
            attribute_name,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db,
        )
        if not stats:
            return json.dumps({"error": f"Attribute '{attribute_name}' not found."})
        return json.dumps(stats)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/edges")
def get_edge_attributes(network_id: int) -> str:
    """Lists available edge attributes with metadata."""
    db = get_db_session()
    try:
        stats = attributes.get_attribute_stats(
            network_id,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db,
        )
        return json.dumps(stats)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/edges/{attribute_name}")
def get_edge_attribute_details(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific edge attribute."""
    db = get_db_session()
    try:
        stats = attributes.get_specific_attribute_stats(
            network_id,
            attribute_name,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db,
        )
        if not stats:
            return json.dumps({"error": f"Attribute '{attribute_name}' not found."})
        return json.dumps(stats)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.resource("network://{network_id}/subgraphs")
def get_subgraphs_resource(network_id: int) -> str:
    """List all subgraphs created from the given parent network."""
    db = get_db_session()
    try:
        subgraphs = network_service.get_subgraphs(db, network_id)
        return json.dumps(subgraphs)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.resource("network://{network_id}/centrality/{metric}/top")
def get_top_nodes_resource(network_id: int, metric: str) -> str:
    """Returns the top 10 nodes based on a centrality metric."""
    db = get_db_session()
    try:
        # Default to k=10 for resource access
        nodes = centrality.get_top_nodes(network_id, metric, 10, db)
        return json.dumps(nodes)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@mcp.resource("network://{network_id}/structure")
def get_structure_resource(network_id: int) -> str:
    """Returns basic structural statistics of the network."""
    db = get_db_session()
    try:
        stats = network_service.get_network_structure(db, network_id)
        return json.dumps(stats)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


# --- Prompts ---

# --- Prompts ---


@mcp.prompt("analyze-structure")
def analyze_structure_prompt(network_id: int) -> list[dict]:
    return prompts.analyze_structure_prompt(network_id)


@mcp.prompt("recommend-visualization")
def recommend_visualization_prompt(network_id: int) -> list[dict]:
    return prompts.recommend_visualization_prompt(network_id)


@mcp.prompt("investigate-attributes")
def investigate_attributes_prompt(network_id: int) -> list[dict]:
    return prompts.investigate_attributes_prompt(network_id)


@mcp.prompt("find-important-nodes")
def find_important_nodes_prompt(network_id: int) -> list[dict]:
    return prompts.find_important_nodes_prompt(network_id)


# --- Tools ---


@mcp.tool()
def initialize_network(network_id: int, graphml_data: str) -> dict:
    """
    Initializes a network from GraphML data.

    Args:
        network_id: The ID of the network record in the database.
        graphml_data: The **raw XML string content** of the GraphML file (not a file path).

    Returns:
        A dictionary containing the initial visualization data and the finalized network ID.
    """
    db = get_db_session()
    # Log the action with truncated data
    truncated_data = (
        graphml_data[:100] + "..." if len(graphml_data) > 100 else graphml_data
    )
    print(
        f"Executing initialize_network for ID {network_id} with data: {truncated_data}"
    )

    try:
        return pipeline.initialize_network_pipeline(network_id, graphml_data, db)
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Error in initialize_network: {e}")
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def calculate_centrality(network_id: int, centrality_type: str) -> str:
    """
    Calculates specific centrality for the network and saves it as a node attribute.

    Args:
        network_id: The ID of the network.
        centrality_type: One of the following:
            - "degree"
            - "betweenness"
            - "closeness"
            - "eigenvector"
            - "pagerank"
    """
    db = get_db_session()
    try:
        centrality.calculate_centrality(network_id, centrality_type, db)
        return f"{centrality_type} centrality calculated."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def calculate_layout(network_id: int, layout_name: str) -> str:
    """
    Calculates a graph layout and saves x, y coordinates as node attributes.

    Args:
        network_id: The ID of the network.
        layout_name: One of the following:
            - "forceatlas2" (Recommended for most networks)
            - "spring"
            - "circle"
            - "kamada_kawai"
            - "shell"
            - "spectral"
            - "spiral"
    """
    db = get_db_session()
    try:
        layout.calculate_layout(network_id, layout_name, db)
        return f"Layout '{layout_name}' calculated and saved."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


from contextlib import contextmanager

from app.schemas.filter import AttributeCondition
from app.schemas.visualization import (
    EdgeColorConfig,
    EdgeWidthConfig,
    NodeColorConfig,
    NodeLabelConfig,
    NodeSizeConfig,
)

# ... imports ...


@contextmanager
def safe_mcp_error_handling(tool_name: str):
    """
    Context manager to catch exceptions, log them with traceback,
    and return a user-friendly error string to the MCP client.
    """
    try:
        yield
    except Exception as e:
        import traceback

        error_msg = f"Error in {tool_name}: {str(e)}"
        print(traceback.format_exc())  # Ensure it goes to stdout/logs
        # You might also want to log to app logger if available
        # logger.error(error_msg, exc_info=True)
        # FastMCP seems to handle return strings as text content,
        # so we return the error message.
        # Note: In a generator/context manager, we can't 'return' a value for the caller
        # in the same way, but the caller (the tool function) should catch this if we re-raise
        # or we rely on the tool function to use this pattern differently.
        # Actually, a decorator is better for return values.
        raise e


# Better approach: Decorator or simple helper wrapper inside functions
def log_and_return_error(func_name: str, e: Exception) -> str:
    import traceback

    traceback.print_exc()
    return f"Error: {str(e)}"


# ...


@mcp.tool()
def generate_visualization(
    network_id: int,
    layout_name: Optional[str] = None,
    focus_network_id: Optional[int] = None,
    node_size_config: Optional[NodeSizeConfig] = None,
    node_color_config: Optional[NodeColorConfig] = None,
    edge_width_config: Optional[EdgeWidthConfig] = None,
    edge_color_config: Optional[EdgeColorConfig] = None,
    context_config: Optional[dict] = None,
    focus_config: Optional[dict] = None,
    node_label_config: Optional[NodeLabelConfig] = None,
    custom_node_colors: Optional[list] = None,
) -> dict:
    """
    Generates the final visualization data (nodes and links) for the frontend.
    Handles layout application, size/color mapping, and focus+context rendering.

    **Coloring Guide**:
    - **Categorical Mapping**: To color specific values explicitly and make others a default color, use:
      `node_color_config={"scale_type": "CATEGORICAL", "attribute": "nationality", "color_map": {"Austrian": "red"}, "default_color": "gray"}`.
      All nodes where nationality="Austrian" will be red. All others (including those with valid other nationalities) will be gray.
      If `default_color` is omitted, other nationalities will be automatically assigned distinct colors from a palette.

    **Note**: Complex configurations (node_color_config, etc.) are now validated strictly.
    Ensure you structure your JSON arguments to match the defined schemas.
    """
    db = get_db_session()
    try:
        # Pydantic models are now passed directly; convert to dict if service expects dict
        # or update service to handle models. For now, dumping to dict is safest to maintain service compatibility.

        vis_args = {
            "network_id": network_id,
            "db": db,
            "layout_name": layout_name,
            "focus_network_id": focus_network_id,
            "node_size_config": node_size_config.model_dump()
            if node_size_config
            else None,
            "node_color_config": node_color_config.model_dump()
            if node_color_config
            else None,
            "edge_width_config": edge_width_config.model_dump()
            if edge_width_config
            else None,
            "edge_color_config": edge_color_config.model_dump()
            if edge_color_config
            else None,
            "context_config": context_config,
            "focus_config": focus_config,
            "node_label_config": node_label_config.model_dump()
            if node_label_config
            else None,
            "custom_node_colors": custom_node_colors,
        }

        return visualizer.generate_visualization_data(**vis_args)
    except Exception as e:
        return log_and_return_error("generate_visualization", e)
    finally:
        db.close()


@mcp.tool()
def create_ego_network(
    source_network_id: int,
    center_node_id: str,
    radius: int,
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """
    Creates an Ego Network subgraph (nodes within radius hops from center).

    Args:
        preserve_layout:
            - True ("Cutout View"): Keeps nodes in their original positions. Use for "zooming in" to see context.
            - False ("Fresh View"): Recalculates layout. Use for analyzing the local structure of the neighborhood.
    """
    db = get_db_session()
    try:
        result = subgraph.create_ego_network(
            source_network_id,
            center_node_id,
            radius,
            db,
            preserve_layout=preserve_layout,
            description=description,
        )
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result
    except Exception as e:
        return log_and_return_error("create_ego_network", e)
    finally:
        db.close()


@mcp.tool()
def create_subgraph_from_nodes(
    source_network_id: int,
    node_ids: List[str],
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """
    Creates a subgraph containing the specified nodes.

    Args:
        preserve_layout:
            - True ("Cutout View"): Keeps original positions.
            - False ("Fresh View"): Recalculates layout.
    """
    db = get_db_session()
    try:
        result = subgraph.create_subgraph_from_nodes(
            source_network_id,
            node_ids,
            db,
            preserve_layout=preserve_layout,
            description=description,
        )
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result
    except Exception as e:
        return log_and_return_error("create_subgraph_from_nodes", e)
    finally:
        db.close()


@mcp.tool()
def create_path_subgraph(
    source_network_id: int,
    source_node_id: str,
    target_node_id: str,
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """
    Creates a subgraph consisting of the shortest path between two nodes.

    Args:
        preserve_layout:
            - True ("Cutout View"): Keeps original positions.
            - False ("Fresh View"): Recalculates layout.
    """
    db = get_db_session()
    try:
        result = subgraph.create_path_subgraph(
            source_network_id,
            source_node_id,
            target_node_id,
            db,
            preserve_layout=preserve_layout,
            description=description,
        )
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result
    except Exception as e:
        return log_and_return_error("create_path_subgraph", e)
    finally:
        db.close()


@mcp.tool()
def create_k_core_subgraph(
    source_network_id: int, k: int, preserve_layout: bool = False, description: str = None
) -> dict:
    """
    Creates a k-Core subgraph (maximal subgraph where every node has degree >= k).

    Args:
        preserve_layout:
            - True ("Cutout View"): Keeps original positions.
            - False ("Fresh View"): Recalculates layout.
    """
    db = get_db_session()
    try:
        result = subgraph.create_k_core_subgraph(
            source_network_id, k, db, preserve_layout=preserve_layout, description=description
        )
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result
    except Exception as e:
        return log_and_return_error("create_k_core_subgraph", e)
    finally:
        db.close()


@mcp.tool()
def create_largest_component_subgraph(
    network_id: int, preserve_layout: bool = False, description: str = None
) -> dict:
    """
    Creates a subgraph from the largest connected component of the network.

    Args:
        preserve_layout:
            - True ("Cutout View"): Keeps original positions.
            - False ("Fresh View"): Recalculates layout.
    """
    db = get_db_session()
    try:
        result = subgraph.create_largest_component_subgraph(
            network_id, db, preserve_layout=preserve_layout, description=description
        )
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result
    except Exception as e:
        return log_and_return_error("create_largest_component_subgraph", e)
    finally:
        db.close()


@mcp.tool()
def create_component_containing_node(
    source_network_id: int,
    node_id: str,
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """
    Creates a subgraph from the connected component containing a specific node.

    Args:
        preserve_layout:
            - True ("Cutout View"): Keeps original positions.
            - False ("Fresh View"): Recalculates layout.
    """
    db = get_db_session()
    try:
        result = subgraph.create_component_containing_node(
            source_network_id,
            node_id,
            db,
            preserve_layout=preserve_layout,
            description=description,
        )
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result
    except Exception as e:
        return log_and_return_error("create_component_containing_node", e)
    finally:
        db.close()


@mcp.tool()
def search_nodes(network_id: int, query: str, attribute: str = None) -> str:
    """
    Searches for nodes in the network by name/label or specific attribute.
    Returns a list of matching nodes with their IDs and names.
    Use this to find node IDs for subgraph creation or analysis.
    """
    db = get_db_session()
    try:
        results = search.search_nodes(
            network_id, query, attribute_name=attribute, db=db
        )
        if not results:
            return "No matching nodes found."

        # Format for LLM readability
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def read_node_details(network_id: int, node_id: str) -> dict:
    """
    Returns full details for a specific node, including all attributes and its description.
    Use this when you need multiple attributes for a single node or need to read its 'desc'.
    """
    db = get_db_session()
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
def create_subgraph_by_attribute_filter(
    network_id: int,
    conditions: List[AttributeCondition],
    suffix: str = "Filtered",
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """
    Creates a new subgraph by filtering nodes from an existing network based on attribute conditions.

    Args:
        network_id: ID of the source network.
        conditions: List of attribute conditions.
          Different conditions in the list are combined with **AND**.
          Inside a condition, `ranges` and `categories` are combined with **OR**.
        suffix: Suffix to append to the new network's name (default: "Filtered").
        preserve_layout:
            - True ("Cutout View"): Keeps original positions.
            - False ("Fresh View"): Recalculates layout.
    """
    db = get_db_session()
    try:
        from app.logic import filter

        # Conditions are already validated Pydantic models (AttributeCondition)
        result = filter.create_subgraph_by_filter(
            network_id,
            conditions,
            suffix,
            db,
            preserve_layout=preserve_layout,
            description=description,
        )
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result
    except Exception as e:
        return log_and_return_error("create_subgraph_by_attribute_filter", e)
    finally:
        db.close()
@mcp.tool()
def get_node_attributes(network_id: int) -> str:
    """
    Lists available node attributes with metadata (type, min/max, distinct values).
    Use this to see what data is available on the nodes before deciding on a visualization.
    """
    db = get_db_session()
    try:
        stats = attributes.get_attribute_stats(
            network_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db,
        )
        return json.dumps(stats)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def get_edge_attributes(network_id: int) -> str:
    """
    Lists available edge attributes with metadata.
    Use this to see what data is available on the edges.
    """
    db = get_db_session()
    try:
        stats = attributes.get_attribute_stats(
            network_id,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db,
        )
        return json.dumps(stats)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def get_network_structure(network_id: int) -> str:
    """
    Returns basic structural statistics of the network (node count, edge count, density).
    Use this to get an overview of the network size and density.
    """
    db = get_db_session()
    try:
        stats = network_service.get_network_structure(db, network_id)
        return json.dumps(stats)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def get_top_centrality_nodes(network_id: int, metric: str, k: int = 10) -> str:
    """
    Returns the top k nodes based on a centrality metric.
    
    Args:
        network_id: The ID of the network.
        metric: One of "degree", "betweenness", "closeness", "eigenvector", "pagerank".
        k: Number of top nodes to return (default: 10).
    """
    db = get_db_session()
    try:
        nodes = centrality.get_top_nodes(network_id, metric, k, db)
        return json.dumps(nodes)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def get_node_attribute_details(network_id: int, attribute_name: str) -> str:
    """
    Returns details and statistics for a specific node attribute.
    Use this when you need to know the distribution or top values of a specific attribute.
    """
    db = get_db_session()
    try:
        stats = attributes.get_specific_attribute_stats(
            network_id,
            attribute_name,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db,
        )
        if not stats:
            return f"Attribute '{attribute_name}' not found."
        return json.dumps(stats)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def get_edge_attribute_details(network_id: int, attribute_name: str) -> str:
    """
    Returns details and statistics for a specific edge attribute.
    Use this when you need to know the distribution or top values of a specific attribute.
    """
    db = get_db_session()
    try:
        stats = attributes.get_specific_attribute_stats(
            network_id,
            attribute_name,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db,
        )
        if not stats:
            return f"Attribute '{attribute_name}' not found."
        return json.dumps(stats)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()
