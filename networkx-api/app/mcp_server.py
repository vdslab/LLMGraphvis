from mcp.server.fastmcp import FastMCP
from app.core import database
from app.logic import importer, layout, centrality, visualizer, attributes, subgraph, exporter
from app import models
import json
from typing import List, Dict, Any, Optional

# Initialize FastMCP Server
mcp = FastMCP("NetworkX Agent", host="0.0.0.0")

def get_db_session():
    """Helper to get a database session."""
    return database.SessionLocal()

@mcp.tool()
def initialize_network(network_id: int, graphml_data: str) -> dict:
    """
    Initializes a network from GraphML data.
    Parses the GraphML, saves it to the database, calculates an initial layout,
    and returns the visualization data.
    """
    db = get_db_session()
    try:
        # 1. Parse and Save
        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        
        # 2. Initial Layout (ForceAtlas2)
        layout.calculate_layout(final_network_id, "forceatlas2", db)
        
        # 3. Initial Visualization
        vis_data = visualizer.generate_visualization_data(final_network_id, db)
        
        return {"network": vis_data, "network_id": final_network_id}
    finally:
        db.close()

@mcp.tool()
def list_node_attributes(network_id: int) -> list:
    """Lists available node attributes with metadata (type, min/max, distinct values)."""
    db = get_db_session()
    try:
        return attributes.get_attribute_stats(
            network_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db
        )
    finally:
        db.close()

@mcp.tool()
def list_edge_attributes(network_id: int) -> list:
    """Lists available edge attributes with metadata."""
    db = get_db_session()
    try:
        return attributes.get_attribute_stats(
            network_id,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db
        )
    finally:
        db.close()

@mcp.tool()
def calculate_centrality(network_id: int, centrality_type: str) -> str:
    """
    Calculates specific centrality for the network and saves it as a node attribute.
    Types: degree, betweenness, closeness, eigenvector, pagerank.
    """
    db = get_db_session()
    try:
        centrality.calculate_centrality(network_id, centrality_type, db)
        return f"{centrality_type} centrality calculated."
    finally:
        db.close()

@mcp.tool()
def calculate_layout(network_id: int, layout_name: str) -> str:
    """
    Calculates a graph layout and saves x, y coordinates as node attributes.
    Layouts: forceatlas2, spring, circle, kamada_kawai, shell, spectral, spiral.
    """
    db = get_db_session()
    try:
        layout.calculate_layout(network_id, layout_name, db)
        return f"Layout '{layout_name}' calculated and saved."
    finally:
        db.close()

@mcp.tool()
def generate_visualization(
    network_id: int,
    layout_name: str = "forceatlas2",
    focus_network_id: Optional[int] = None,
    node_size_config: Optional[dict] = None,
    node_color_config: Optional[dict] = None,
    edge_width_config: Optional[dict] = None,
    edge_color_config: Optional[dict] = None,
    context_config: Optional[dict] = None,
    focus_config: Optional[dict] = None,
    node_label_config: Optional[dict] = None,
    custom_node_colors: Optional[list] = None
) -> dict:
    """
    Generates the final visualization data (nodes and links) for the frontend.
    Handles layout application, size/color mapping, and focus+context rendering.
    """
    db = get_db_session()
    try:
        # Removed auto-layout calculation logic. 
        # The visualizer.generate_visualization_data will raise ValueError if layout is missing.
            
        return visualizer.generate_visualization_data(
            network_id, 
            db, 
            layout_name=layout_name,
            node_size_config=node_size_config,
            node_color_config=node_color_config,
            edge_width_config=edge_width_config,
            edge_color_config=edge_color_config,
            focus_network_id=focus_network_id,
            context_config=context_config,
            focus_config=focus_config,
            node_label_config=node_label_config,
            custom_node_colors=custom_node_colors
        )
    finally:
        db.close()

@mcp.tool()
def create_ego_network(source_network_id: int, center_node_id: str, radius: int) -> dict:
    """Creates an Ego Network subgraph (nodes within radius hops from center)."""
    db = get_db_session()
    try:
        return subgraph.create_ego_network(source_network_id, center_node_id, radius, db)
    finally:
        db.close()

@mcp.tool()
def create_subgraph_from_nodes(source_network_id: int, node_ids: List[str]) -> dict:
    """Creates a subgraph containing the specified nodes."""
    db = get_db_session()
    try:
        return subgraph.create_subgraph_from_nodes(source_network_id, node_ids, db)
    finally:
        db.close()

@mcp.tool()
def create_path_subgraph(source_network_id: int, source_node_id: str, target_node_id: str) -> dict:
    """Creates a subgraph consisting of the shortest path between two nodes."""
    db = get_db_session()
    try:
        return subgraph.create_path_subgraph(source_network_id, source_node_id, target_node_id, db)
    finally:
        db.close()

@mcp.tool()
def create_k_core_subgraph(source_network_id: int, k: int) -> dict:
    """Creates a k-Core subgraph (maximal subgraph where every node has degree >= k)."""
    db = get_db_session()
    try:
        return subgraph.create_k_core_subgraph(source_network_id, k, db)
    finally:
        db.close()

@mcp.tool()
def create_largest_component_subgraph(source_network_id: int) -> dict:
    """Creates a subgraph from the largest connected component of the network."""
    db = get_db_session()
    try:
        return subgraph.create_largest_component_subgraph(source_network_id, db)
    finally:
        db.close()

@mcp.tool()
def get_subgraphs(network_id: int) -> list:
    """List all subgraphs created from the given parent network."""
    db = get_db_session()
    try:
        subgraphs = db.query(models.Network).filter(models.Network.parent_network_id == network_id).all()
        return [{"id": s.id, "name": s.name, "created_at": str(s.created_at)} for s in subgraphs]
    finally:
        db.close()

@mcp.tool()
def get_top_nodes(network_id: int, metric: str, k: int = 10) -> list:
    """Returns the top K nodes based on a centrality metric."""
    db = get_db_session()
    try:
        return centrality.get_top_nodes(network_id, metric, k, db)
    finally:
        db.close()

@mcp.tool()
def export_network(network_id: int) -> str:
    """Exports the network to GraphML format."""
    db = get_db_session()
    try:
        return exporter.export_network_to_graphml(network_id, db)
    finally:
        db.close()
