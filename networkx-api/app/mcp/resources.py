from app.core.mcp import mcp
from app.core import database
from app.logic import network_metadata, attributes, subgraph, centrality

# --- Resources ---

@mcp.resource("network://{network_id}/metadata")
def get_network_metadata(network_id: int) -> str:
    """Returns network metadata (name, description, created_at) as JSON."""
    db = database.SessionLocal()
    try:
        return network_metadata.get_metadata(db, network_id)
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/nodes")
def get_node_attributes_resource(network_id: int) -> str:
    """Lists available node attributes with metadata (type, min/max, distinct values)."""
    db = database.SessionLocal()
    try:
        return attributes.get_node_attributes_overview(db, network_id)
    finally:
        db.close()

@mcp.resource("network://{network_id}/attributes/nodes/{attribute_name}")
def get_node_attribute_details_resource(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific node attribute."""
    db = database.SessionLocal()
    try:
        return attributes.get_node_attribute_details(db, network_id, attribute_name)
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/edges")
def get_edge_attributes_resource(network_id: int) -> str:
    """Lists available edge attributes with metadata."""
    db = database.SessionLocal()
    try:
        return attributes.get_edge_attributes_overview(db, network_id)
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/edges/{attribute_name}")
def get_edge_attribute_details_resource(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific edge attribute."""
    db = database.SessionLocal()
    try:
        return attributes.get_edge_attribute_details(db, network_id, attribute_name)
    finally:
        db.close()


@mcp.resource("network://{network_id}/subgraphs")
def get_subgraphs_resource(network_id: int) -> str:
    """List all subgraphs created from the given parent network."""
    db = database.SessionLocal()
    try:
        return subgraph.list_subgraphs(db, network_id)
    finally:
        db.close()


@mcp.resource("network://{network_id}/top_nodes/{metric}")
def get_top_nodes_resource(network_id: int, metric: str) -> str:
    """Returns the top 10 nodes based on a centrality metric."""
    db = database.SessionLocal()
    try:
        return centrality.get_top_nodes(db, network_id, metric)
    finally:
        db.close()


@mcp.resource("network://{network_id}/structure")
def get_structure_resource(network_id: int) -> str:
    """Returns basic structural statistics of the network."""
    db = database.SessionLocal()
    try:
        from app.logic import structure 
        return structure.get_structure_stats(db, network_id)
    finally:
        db.close()
