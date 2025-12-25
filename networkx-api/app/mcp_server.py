import json
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from common import models
from app.core import database
from app.logic import (
    attributes,
    centrality,
    community,
    layout,
    network_metadata,
    pipeline,
    prompts,
    search,
    subgraph,
    visualizer,
)
from contextlib import contextmanager

from app.schemas.filter import AttributeCondition
from app.schemas.visualization import (
    EdgeColorConfig,
    EdgeWidthConfig,
    NodeColorConfig,
    NodeLabelConfig,
    NodeSizeConfig,
)

# Initialize FastMCP Server
mcp = FastMCP("NetworkX Agent", host="0.0.0.0")


def execute_with_db(func, *args, **kwargs):
    """Executes a function with a database session injected."""
    db = database.SessionLocal()
    try:
        return func(db=db, *args, **kwargs)
    except Exception as e:
        import traceback

        traceback.print_exc()
        if isinstance(e, ValueError):
            return f"Error: {str(e)}"
        return f"System Error: {str(e)}"
    finally:
        db.close()


@mcp.tool()
def update_network_metadata(
    network_id: int, description: str = None, name: str = None
) -> str:
    """Updates the network's name or description."""
    return execute_with_db(
        network_metadata.update_network_metadata,
        network_id=network_id,
        description=description,
        name=name,
    )


@mcp.resource("network://{network_id}/metadata")
def get_network_metadata(network_id: int) -> str:
    """Returns network metadata (name, description, created_at) as JSON."""

    def _logic(db, network_id):
        metadata = network_metadata.get_network_metadata(db, network_id)
        return json.dumps(metadata)

    return execute_with_db(_logic, network_id=network_id)


@mcp.resource("network://{network_id}/attributes/nodes")
def get_node_attributes_resource(network_id: int) -> str:
    """Lists available node attributes with metadata (type, min/max, distinct values)."""

    def _logic(db, network_id):
        stats = attributes.get_attribute_stats(
            network_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db,
        )
        return json.dumps(stats)

    return execute_with_db(_logic, network_id=network_id)


@mcp.resource("network://{network_id}/attributes/nodes/{attribute_name}")
def get_node_attribute_details_resource(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific node attribute."""

    def _logic(db, network_id, attribute_name):
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

    return execute_with_db(
        _logic, network_id=network_id, attribute_name=attribute_name
    )


@mcp.resource("network://{network_id}/attributes/edges")
def get_edge_attributes_resource(network_id: int) -> str:
    """Lists available edge attributes with metadata."""

    def _logic(db, network_id):
        stats = attributes.get_attribute_stats(
            network_id,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db,
        )
        return json.dumps(stats)

    return execute_with_db(_logic, network_id=network_id)


@mcp.resource("network://{network_id}/attributes/edges/{attribute_name}")
def get_edge_attribute_details_resource(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific edge attribute."""

    def _logic(db, network_id, attribute_name):
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

    return execute_with_db(
        _logic, network_id=network_id, attribute_name=attribute_name
    )


@mcp.resource("network://{network_id}/subgraphs")
def get_subgraphs_resource(network_id: int) -> str:
    """List all subgraphs created from the given parent network."""

    def _logic(db, network_id):
        subgraphs = network_metadata.get_subgraphs(db, network_id)
        return json.dumps(subgraphs)

    return execute_with_db(_logic, network_id=network_id)


@mcp.resource("network://{network_id}/centrality/{metric}/top")
def get_top_nodes_resource(network_id: int, metric: str) -> str:
    """Returns the top 10 nodes based on a centrality metric."""

    def _logic(db, network_id, metric):
        nodes = centrality.get_top_nodes(network_id, metric, 10, db)
        return json.dumps(nodes)

    return execute_with_db(_logic, network_id=network_id, metric=metric)


@mcp.resource("network://{network_id}/structure")
def get_structure_resource(network_id: int) -> str:
    """Returns basic structural statistics of the network."""

    def _logic(db, network_id):
        stats = network_metadata.get_network_structure(db, network_id)
        return json.dumps(stats)

    return execute_with_db(_logic, network_id=network_id)


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
    """
    truncated_data = (
        graphml_data[:100] + "..." if len(graphml_data) > 100 else graphml_data
    )
    print(
        f"Executing initialize_network for ID {network_id} with data: {truncated_data}"
    )

    return execute_with_db(
        pipeline.initialize_network_pipeline,
        network_id=network_id,
        graphml_data=graphml_data,
    )


@mcp.tool()
def calculate_centrality(network_id: int, centrality_type: str) -> str:
    """Calculates specific centrality for the network."""

    def _logic(db, network_id, centrality_type):
        centrality.calculate_centrality(network_id, centrality_type, db)
        return f"{centrality_type} centrality calculated. Saved as node attribute '{centrality_type}_centrality'."

    return execute_with_db(
        _logic, network_id=network_id, centrality_type=centrality_type
    )


@mcp.tool()
def calculate_community(network_id: int, algorithm: str = "louvain") -> str:
    """Detects communities in the network."""

    def _logic(db, network_id, algorithm):
        attr_name = community.calculate_community(network_id, algorithm, db)
        return f"Community detection ({algorithm}) completed. Saved as node attribute '{attr_name}'."

    return execute_with_db(_logic, network_id=network_id, algorithm=algorithm)


@mcp.tool()
def calculate_layout(network_id: int, layout_name: str) -> str:
    """Calculates a graph layout and saves x, y coordinates as node attributes."""

    def _logic(db, network_id, layout_name):
        layout.calculate_layout(network_id, layout_name, db)
        return f"Layout '{layout_name}' calculated and saved."

    return execute_with_db(_logic, network_id=network_id, layout_name=layout_name)


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
    """Generates the final visualization data."""

    def _logic(db, **kwargs):
        # Convert Pydantic models to dict if necessary, or pass them as is if service handles it.
        # But wait, execute_with_db passes kwargs directly.
        # We need to process models dump here.
        processed_kwargs = {
            "network_id": kwargs["network_id"],
            "db": db,
            "layout_name": kwargs.get("layout_name"),
            "focus_network_id": kwargs.get("focus_network_id"),
            "context_config": kwargs.get("context_config"),
            "focus_config": kwargs.get("focus_config"),
            "custom_node_colors": kwargs.get("custom_node_colors"),
        }

        # Handling Pydantic models
        for key in [
            "node_size_config",
            "node_color_config",
            "edge_width_config",
            "edge_color_config",
            "node_label_config",
        ]:
            val = kwargs.get(key)
            processed_kwargs[key] = val.model_dump() if val else None

        return visualizer.generate_visualization_data(**processed_kwargs)

    # We must pass the arguments to execute_with_db, which passes them to _logic
    return execute_with_db(
        _logic,
        network_id=network_id,
        layout_name=layout_name,
        focus_network_id=focus_network_id,
        node_size_config=node_size_config,
        node_color_config=node_color_config,
        edge_width_config=edge_width_config,
        edge_color_config=edge_color_config,
        context_config=context_config,
        focus_config=focus_config,
        node_label_config=node_label_config,
        custom_node_colors=custom_node_colors,
    )


@mcp.tool()
def create_ego_network(
    source_network_id: int,
    center_node_id: str,
    radius: int,
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """Creates an Ego Network subgraph."""

    def _logic(db, **kwargs):
        result = subgraph.create_ego_network(db=db, **kwargs)
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result

    return execute_with_db(
        _logic,
        source_network_id=source_network_id,
        center_node_id=center_node_id,
        radius=radius,
        preserve_layout=preserve_layout,
        description=description,
    )


@mcp.tool()
def create_subgraph_from_nodes(
    source_network_id: int,
    node_ids: List[str],
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """Creates a subgraph containing the specified nodes."""

    def _logic(db, **kwargs):
        result = subgraph.create_subgraph_from_nodes(db=db, **kwargs)
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result

    return execute_with_db(
        _logic,
        source_network_id=source_network_id,
        node_ids=node_ids,
        preserve_layout=preserve_layout,
        description=description,
    )


@mcp.tool()
def create_path_subgraph(
    source_network_id: int,
    source_node_id: str,
    target_node_id: str,
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """Creates a subgraph consisting of the shortest path between two nodes."""

    def _logic(db, **kwargs):
        result = subgraph.create_path_subgraph(db=db, **kwargs)
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result

    return execute_with_db(
        _logic,
        source_network_id=source_network_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        preserve_layout=preserve_layout,
        description=description,
    )


@mcp.tool()
def create_k_core_subgraph(
    source_network_id: int,
    k: int,
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """Creates a k-Core subgraph."""

    def _logic(db, **kwargs):
        result = subgraph.create_k_core_subgraph(db=db, **kwargs)
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result

    return execute_with_db(
        _logic,
        source_network_id=source_network_id,
        k=k,
        preserve_layout=preserve_layout,
        description=description,
    )


@mcp.tool()
def create_largest_component_subgraph(
    source_network_id: int, preserve_layout: bool = False, description: str = None
) -> dict:
    """Creates a subgraph from the largest connected component."""

    def _logic(db, **kwargs):
        result = subgraph.create_largest_component_subgraph(db=db, **kwargs)
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result

    return execute_with_db(
        _logic,
        source_network_id=source_network_id,
        preserve_layout=preserve_layout,
        description=description,
    )


@mcp.tool()
def create_component_containing_node(
    source_network_id: int,
    node_id: str,
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """Creates a subgraph from the connected component containing a specific node."""

    def _logic(db, **kwargs):
        result = subgraph.create_component_containing_node(db=db, **kwargs)
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result

    return execute_with_db(
        _logic,
        source_network_id=source_network_id,
        node_id=node_id,
        preserve_layout=preserve_layout,
        description=description,
    )


@mcp.tool()
def search_nodes(network_id: int, query: str, attribute: str = None) -> str:
    """Searches for nodes in the network."""

    def _logic(db, network_id, query, attribute):
        results = search.search_nodes(
            network_id, query, attribute_name=attribute, db=db
        )
        if not results:
            return "No matching nodes found."
        return json.dumps(results, indent=2)

    return execute_with_db(
        _logic, network_id=network_id, query=query, attribute=attribute
    )


@mcp.tool()
def read_node_details(network_id: int, node_id: str) -> dict:
    """Returns full details for a specific node."""

    def _logic(db, network_id, node_id):
        details = search.get_node_details(network_id, node_id, db)
        if not details:
            return {"error": f"Node '{node_id}' not found in network {network_id}."}
        return details

    return execute_with_db(_logic, network_id=network_id, node_id=node_id)


@mcp.tool()
def create_subgraph_by_attribute_filter(
    network_id: int,
    conditions: List[AttributeCondition],
    suffix: str = "Filtered",
    preserve_layout: bool = False,
    description: str = None,
) -> dict:
    """Creates a new subgraph by filtering nodes based on attribute conditions."""

    def _logic(db, **kwargs):
        from app.logic import filter

        result = filter.create_subgraph_by_filter(db=db, **kwargs)
        if "new_network_id" in result:
            result["network_id"] = result["new_network_id"]
        return result

    return execute_with_db(
        _logic,
        network_id=network_id,
        conditions=conditions,
        suffix=suffix,
        preserve_layout=preserve_layout,
        description=description,
    )


# --- Renamed Tools to avoid collision with Resources and be more explicit ---


@mcp.tool()
def list_node_attributes(network_id: int) -> str:
    """
    Lists available node attributes with metadata (type, min/max, distinct values).
    Use this to see what data is available on the nodes before deciding on a visualization.
    """
    return get_node_attributes_resource(network_id)


@mcp.tool()
def list_edge_attributes(network_id: int) -> str:
    """
    Lists available edge attributes with metadata.
    Use this to see what data is available on the edges.
    """
    return get_edge_attributes_resource(network_id)


@mcp.tool()
def get_network_structure_tool(network_id: int) -> str:
    """
    Returns basic structural statistics of the network (node count, edge count, density).
    """
    return get_structure_resource(network_id)


@mcp.tool()
def get_top_centrality_nodes(network_id: int, metric: str, k: int = 10) -> str:
    """Returns the top k nodes based on a centrality metric."""
    return execute_with_db(
        lambda db: json.dumps(centrality.get_top_nodes(network_id, metric, k, db))
    )


@mcp.tool()
def get_node_attribute_details_tool(network_id: int, attribute_name: str) -> str:
    """Returns details and statistics for a specific node attribute."""
    return get_node_attribute_details_resource(network_id, attribute_name)


@mcp.tool()
def get_visualization_state(network_id: int) -> str:
    """
    Returns the current visualization configuration and color/size mappings.
    Use this to answer questions about what the user sees (e.g., "What color is Community 0?", "Which is larger?").
    """
    def _logic(db, network_id):
        state = network_metadata.get_visualization_state(db, network_id)
        return json.dumps(state, indent=2)

    return execute_with_db(_logic, network_id=network_id)
