from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core import database
from common import models
import logging

logger = logging.getLogger(__name__)

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
        from app.logic import search
        nodes = search.search_nodes(network_id, query, limit=limit, db=db)
        return f"Found {len(nodes)} nodes: {nodes}"
    except Exception as e:
        logger.error(f"search_nodes failed: {e}")
        return f"Error: {type(e).__name__}: {str(e)}"
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
