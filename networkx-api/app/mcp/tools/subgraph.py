from typing import List, Optional, Dict, Any, Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core import database
import logging
import traceback

logger = logging.getLogger(__name__)

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
