from typing import Any, Dict, List, Union

from app.core import database
from app.core.logging import get_logger
from app.core.mcp import mcp
from app.logic import attributes, centrality, network_metadata

from common import models

logger = get_logger(__name__)

# Resources return JSON objects, not prose. The backend (llm/context.py) only
# parses a resource body when the server declares it as JSON, so an omitted
# mime_type here silently blanks the network context in the system prompt and
# the post-upload overview shown to the user.
JSON_MIME = "application/json"

ResourceResult = Union[Dict[str, Any], List[Dict[str, Any]]]


def _error(uri: str, exc: Exception) -> Dict[str, str]:
    """Log and wrap a failure so the caller can tell it apart from empty data."""
    logger.error(f"Error reading resource {uri}: {exc}", exc_info=True)
    return {"error": str(exc)}


# --- Resources ---

@mcp.resource("network://{network_id}/metadata", mime_type=JSON_MIME)
def get_network_metadata(network_id: int) -> ResourceResult:
    """Returns network metadata (name, description, created_at) as JSON."""
    db = database.SessionLocal()
    try:
        return network_metadata.get_network_metadata(db, network_id)
    except Exception as e:
        return _error(f"network://{network_id}/metadata", e)
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/nodes", mime_type=JSON_MIME)
def get_node_attributes_resource(network_id: int) -> ResourceResult:
    """Lists available node attributes with metadata (type, min/max, distinct values)."""
    db = database.SessionLocal()
    try:
        return network_metadata.list_node_attributes(db, network_id)
    except Exception as e:
        return _error(f"network://{network_id}/attributes/nodes", e)
    finally:
        db.close()


@mcp.resource(
    "network://{network_id}/attributes/nodes/{attribute_name}", mime_type=JSON_MIME
)
def get_node_attribute_details_resource(
    network_id: int, attribute_name: str
) -> ResourceResult:
    """Returns details and stats for a specific node attribute."""
    db = database.SessionLocal()
    try:
        details = attributes.get_specific_attribute_stats(
            network_id,
            attribute_name,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db,
        )
        if details is None:
            raise ValueError(
                f"Node attribute '{attribute_name}' not found for network {network_id}"
            )
        return details
    except Exception as e:
        return _error(
            f"network://{network_id}/attributes/nodes/{attribute_name}", e
        )
    finally:
        db.close()


@mcp.resource("network://{network_id}/attributes/edges", mime_type=JSON_MIME)
def get_edge_attributes_resource(network_id: int) -> ResourceResult:
    """Lists available edge attributes with metadata."""
    db = database.SessionLocal()
    try:
        return network_metadata.list_edge_attributes(db, network_id)
    except Exception as e:
        return _error(f"network://{network_id}/attributes/edges", e)
    finally:
        db.close()


@mcp.resource(
    "network://{network_id}/attributes/edges/{attribute_name}", mime_type=JSON_MIME
)
def get_edge_attribute_details_resource(
    network_id: int, attribute_name: str
) -> ResourceResult:
    """Returns details and stats for a specific edge attribute."""
    db = database.SessionLocal()
    try:
        details = attributes.get_specific_attribute_stats(
            network_id,
            attribute_name,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db,
        )
        if details is None:
            raise ValueError(
                f"Edge attribute '{attribute_name}' not found for network {network_id}"
            )
        return details
    except Exception as e:
        return _error(
            f"network://{network_id}/attributes/edges/{attribute_name}", e
        )
    finally:
        db.close()


@mcp.resource("network://{network_id}/subgraphs", mime_type=JSON_MIME)
def get_subgraphs_resource(network_id: int) -> ResourceResult:
    """List all subgraphs created from the given parent network."""
    db = database.SessionLocal()
    try:
        # Use network_metadata logic for listing
        return network_metadata.get_subgraphs(db, network_id)
    except Exception as e:
        return _error(f"network://{network_id}/subgraphs", e)
    finally:
        db.close()


@mcp.resource("network://{network_id}/top_nodes/{metric}", mime_type=JSON_MIME)
def get_top_nodes_resource(network_id: int, metric: str) -> ResourceResult:
    """Returns the top 10 nodes based on a centrality metric."""
    db = database.SessionLocal()
    try:
        return centrality.get_top_nodes(network_id, metric, 10, "desc", db)
    except Exception as e:
        return _error(f"network://{network_id}/top_nodes/{metric}", e)
    finally:
        db.close()


@mcp.resource("network://{network_id}/structure", mime_type=JSON_MIME)
def get_structure_resource(network_id: int) -> ResourceResult:
    """Returns basic structural statistics of the network."""
    db = database.SessionLocal()
    try:
        return network_metadata.get_network_structure(db, network_id)
    except Exception as e:
        return _error(f"network://{network_id}/structure", e)
    finally:
        db.close()
