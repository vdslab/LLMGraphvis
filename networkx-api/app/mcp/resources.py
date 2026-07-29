from app.core.mcp import mcp
from app.core import database
from app.logic import network_metadata, attributes, subgraph, centrality

# --- Resources ---

@mcp.resource("network://{network_id}/metadata")
def get_network_metadata(network_id: int) -> str:
    """Returns network metadata (name, description, created_at) as JSON."""
    db = database.SessionLocal()
    try:
        return network_metadata.get_network_metadata(db, network_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/nodes")
def get_node_attributes_resource(network_id: int) -> str:
    """Lists available node attributes with metadata (type, min/max, distinct values)."""
    db = database.SessionLocal()
    try:
        return attributes.get_node_attributes_overview(db, network_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

@mcp.resource("network://{network_id}/attributes/nodes/{attribute_name}")
def get_node_attribute_details_resource(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific node attribute."""
    db = database.SessionLocal()
    try:
        return attributes.get_node_attribute_details(db, network_id, attribute_name)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/edges")
def get_edge_attributes_resource(network_id: int) -> str:
    """Lists available edge attributes with metadata."""
    db = database.SessionLocal()
    try:
        return attributes.get_edge_attributes_overview(db, network_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/edges/{attribute_name}")
def get_edge_attribute_details_resource(network_id: int, attribute_name: str) -> str:
    """Returns details and stats for a specific edge attribute."""
    db = database.SessionLocal()
    try:
        return attributes.get_edge_attribute_details(db, network_id, attribute_name)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.resource("network://{network_id}/subgraphs")
def get_subgraphs_resource(network_id: int) -> str:
    """List all subgraphs created from the given parent network."""
    db = database.SessionLocal()
    try:
        # Use network_metadata logic for listing
        return network_metadata.get_subgraphs(db, network_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.resource("network://{network_id}/top_nodes/{metric}")
def get_top_nodes_resource(network_id: int, metric: str) -> str:
    """Returns the top 10 nodes based on a centrality metric."""
    db = database.SessionLocal()
    try:
        return centrality.get_top_nodes(network_id, metric, 10, "desc", db)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@mcp.resource("network://{network_id}/structure")
def get_structure_resource(network_id: int) -> str:
    """Returns basic structural statistics of the network."""
    db = database.SessionLocal()
    try:
        # Using network_metadata for structural stats if available, or structure module?
        # Checked network_metadata.py, it HAS get_network_structure!
        return network_metadata.get_network_structure(db, network_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
