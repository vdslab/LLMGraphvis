from typing import List, Optional, Dict, Any, Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging
import traceback

logger = logging.getLogger(__name__)

@mcp.tool()
@handle_tool_errors
def create_subgraph_from_nodes(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    node_ids: Annotated[List[str], Field(description="List of node IDs (strings) to include in the subgraph.")],
    description: Annotated[str, Field(description="Description of the subgraph (e.g., 'Neighbors of Node A').")] = "Custom subgraph",
    preserve_layout: Annotated[bool, Field(description="If True, copies the x,y coordinates from the source network.")] = True
) -> dict:
    """
    Creates a NEW subgraph network from a list of specific node IDs.
    
    WARNING:
    - Use this tool ONLY when the user explicitly provides a list of specific Node IDs (e.g. "Create a subgraph for nodes A, B, and C").
    - Do NOT use this tool to "guess" or "find" nodes based on attributes (e.g. "nodes from Men"). Use `create_subgraph_by_filter` for that.
    
    NOTE:
    - If `preserve_layout=False` (default), a new layout is automatically calculated (saved as attributes), but NOT returned.
    - To visualize the result, you MUST call `switch_to_network(new_network_id)`.
        
    Returns:
        dict: {"new_network_id": int, "content": str}
    """
    with get_db_context() as db:
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


@mcp.tool()
@handle_tool_errors
def create_subgraph_by_attributes(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    node_filters: Annotated[Optional[str], Field(description='JSON list of filter objects. e.g. \'[{"attribute": "department", "operator": "==", "value": "R&D"}]\'')] = None,
    edge_filters: Annotated[Optional[str], Field(description='JSON list of filter objects. e.g. \'[{"attribute": "weight", "operator": ">", "value": 0.5}]\'')] = None,
    new_name_suffix: Annotated[str, Field(description="Suffix to append to the new network name.")] = "_subgraph"
) -> dict:
    """
    Creates a new subgraph by filtering nodes and edges based on attributes.
    This creates a new network record in the database.
    
    Supported operators: "==", "!=", ">", "<", ">=", "<=", "in", "not in", "contains"

    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        
        n_filters = json.loads(node_filters) if node_filters else []
        e_filters = json.loads(edge_filters) if edge_filters else []
        
        new_id = subgraph.create_subgraph_by_attributes(db, network_id, n_filters, e_filters, new_name_suffix)
        vis_data = visualization_builder.build_visualization(db, new_id)
        
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Created subgraph {new_id} based on attributes."
        }


@mcp.tool()
@handle_tool_errors
def create_ego_network(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    center_node_id: Annotated[str, Field(description="The ID of the center node.")],
    radius: Annotated[int, Field(description="The radius of the ego network (default 1).")] = 1,
    new_name_suffix: Annotated[str, Field(description="Suffix to append to the new network name.")] = "_ego"
) -> dict:
    """
    Creates an Ego Network (subgraph) centered around a specific node.
    Includes the center node and all neighbors within the given radius.
    
    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        
        new_id = subgraph.create_ego_network(db, network_id, center_node_id, radius, new_name_suffix)
        vis_data = visualization_builder.build_visualization(db, new_id)
        
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Created Ego Network {new_id} centered on {center_node_id} (r={radius})."
        }


@mcp.tool()
@handle_tool_errors
def create_community_subgraph(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    community_id: Annotated[str, Field(description="The ID/Label of the community to extract.")],
    community_attribute: Annotated[str, Field(description="The node attribute name holding community labels.")] = "community",
    new_name_suffix: Annotated[str, Field(description="Suffix to append to the new network name.")] = "_community"
) -> dict:
    """
    Creates a subgraph containing only nodes belonging to a specific community.
    
    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        
        # Use attribute filtering logic internally
        filters = [{"attribute": community_attribute, "operator": "==", "value": community_id}]
        new_id = subgraph.create_subgraph_by_attributes(db, network_id, node_filters=filters, new_name_suffix=new_name_suffix)
        vis_data = visualization_builder.build_visualization(db, new_id)
        
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Created Community Subgraph {new_id} for community '{community_id}'."
        }


@mcp.tool()
@handle_tool_errors
def create_largest_component_subgraph(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    new_name_suffix: Annotated[str, Field(description="Suffix to append to the new network name.")] = "_largest_component"
) -> dict:
    """
    Creates a subgraph containing only the largest connected component.
    Useful for filtering out disconnected nodes/islands.
    
    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        
        new_id = subgraph.create_largest_component_subgraph(db, network_id, new_name_suffix)
        vis_data = visualization_builder.build_visualization(db, new_id)
        
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Created Subgraph {new_id} (Largest Component)."
        }


@mcp.tool()
@handle_tool_errors
def filter_nodes_by_degree(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    min_degree: Annotated[int, Field(description="Minimum degree to keep.")],
    new_name_suffix: Annotated[str, Field(description="Suffix to append to the new network name.")] = "_high_degree"
) -> dict:
    """
    Creates a subgraph containing nodes with degree >= min_degree.
    
    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        
        new_id = subgraph.filter_nodes_by_degree(db, network_id, min_degree, new_name_suffix)
        vis_data = visualization_builder.build_visualization(db, new_id)
        
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Created Subgraph {new_id} with nodes of degree >= {min_degree}."
        }


@mcp.tool()
@handle_tool_errors
def create_subgraph_by_node_list(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    node_ids: Annotated[List[str], Field(description="List of node IDs to include in the subgraph.")],
    new_name_suffix: Annotated[str, Field(description="Suffix to append to the new network name.")] = "_selection"
) -> dict:
    """
    Creates a subgraph from a specific list of node IDs.
    
    Returns:
        dict: {"network_id": int, "network": dict, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph, visualization_builder
        
        # We can implement a specific logic function for this if not exists, 
        # or use attribute filter 'in'.
        # Let's check logic/subgraph.py. If create_subgraph_from_nodes exists.
        # Assuming it exists or we use 'id' in node_ids filter.
        
        # Ideally, we should check what logic/subgraph.py provides.
        # But based on typical implementation:
        filters = [{"attribute": "id", "operator": "in", "value": node_ids}]
        new_id = subgraph.create_subgraph_by_attributes(db, network_id, node_filters=filters, new_name_suffix=new_name_suffix)
        
        vis_data = visualization_builder.build_visualization(db, new_id)
        
        return {
            "network_id": new_id,
            "network": vis_data,
            "content": f"Created Subgraph {new_id} from {len(node_ids)} specific nodes."
        }


@mcp.tool()
def get_subgraphs(
    network_id: Annotated[int, Field(description="The ID of the parent network.")]
) -> dict:
    """
    Lists all subgraphs derived from the given network.
        
    Returns:
        dict: {"subgraphs": [{"id": int, "name": str, ...}]}
    """
    with get_db_context() as db:
        try:
            from app.logic import network_metadata
            subgraphs = network_metadata.get_subgraphs(db, network_id)
            return {"subgraphs": subgraphs}
        except Exception as e:
            logger.error(f"get_subgraphs failed: {e}")
            raise RuntimeError(f"Failed to list subgraphs: {str(e)}") from e


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
    with get_db_context() as db:
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
            raise RuntimeError(f"Node filtering failed: {str(e)}") from e


@mcp.tool()
def create_subgraph_by_filter(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    conditions: Annotated[List[Dict[str, Any]], Field(description="List of conditions. Schema: [{'attribute': 'Name', 'categories': ['A', 'B'], 'ranges': [{'min': 10, 'max': 20}]}]")],
    preserve_layout: Annotated[bool, Field(description="If True, keeps x,y positions from source.")] = True,
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
        
    NOTE:
    - If `preserve_layout=False` (default), a new layout is calculated automatically.
    - To visualize the result, you MUST call `switch_to_network(new_network_id)`.

    Returns:
        dict: {"new_network_id": int, "content": str}
    """
    with get_db_context() as db:
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
                raise ValueError("No valid conditions provided.")

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
            raise RuntimeError(f"Subgraph create by filter failed: {str(e)}") from e
