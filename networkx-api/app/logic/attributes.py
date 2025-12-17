from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from typing import Dict, List, Any, Optional, Type

from app import models
from app.core.logging import get_logger

logger = get_logger(__name__)

# --- Attributes Helper Functions ---

def clear_network_data(network_id: int, db: Session) -> None:
    """
    Clears all graph data (nodes, edges, attribute values) for a network.
    Does NOT delete the Network record itself or Attribute Definitions (to preserve schema if reused).
    
    Args:
        network_id: The ID of the network to clear.
        db: Database session.
    """
    logger.info(f"Clearing network data for network_id={network_id}")
    
    # 1. Delete Edge Attribute Values (and their children)
    # Get all EdgeAttributeValue IDs for this network
    edge_attr_val_ids = [
        r[0] for r in db.query(models.EdgeAttributeValue.id)
        .join(models.Edge)
        .filter(models.Edge.network_id == network_id)
        .all()
    ]
    
    if edge_attr_val_ids:
        db.query(models.EdgeFloatAttributeValue).filter(
            models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(edge_attr_val_ids)
        ).delete(synchronize_session=False)
        
        db.query(models.EdgeTextAttributeValue).filter(
            models.EdgeTextAttributeValue.edge_attribute_value_id.in_(edge_attr_val_ids)
        ).delete(synchronize_session=False)
        
        db.query(models.EdgeAttributeValue).filter(
            models.EdgeAttributeValue.id.in_(edge_attr_val_ids)
        ).delete(synchronize_session=False)

    # 2. Delete Node Attribute Values (and their children)
    # Get all NodeAttributeValue IDs
    node_attr_val_ids = [
        r[0] for r in db.query(models.NodeAttributeValue.id)
        .join(models.Node)
        .filter(models.Node.network_id == network_id)
        .all()
    ]
    
    if node_attr_val_ids:
        db.query(models.NodeFloatAttributeValue).filter(
            models.NodeFloatAttributeValue.node_attribute_value_id.in_(node_attr_val_ids)
        ).delete(synchronize_session=False)
        
        db.query(models.NodeTextAttributeValue).filter(
            models.NodeTextAttributeValue.node_attribute_value_id.in_(node_attr_val_ids)
        ).delete(synchronize_session=False)
        
        db.query(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.id.in_(node_attr_val_ids)
        ).delete(synchronize_session=False)

    # 3. Delete Edges
    db.query(models.Edge).filter(models.Edge.network_id == network_id).delete(synchronize_session=False)

    # 4. Delete Nodes
    db.query(models.Node).filter(models.Node.network_id == network_id).delete(synchronize_session=False)
    
    db.commit()


def ensure_attributes(
    network_id: int, 
    attr_types: Dict[str, str], 
    model_class: Type[models.Base], 
    db: Session, 
    commit: bool = True, 
    descriptions: Optional[Dict[str, str]] = None
) -> Dict[str, int]:
    """
    Ensure attributes exist for the given keys and return a map of {name: id}.
    
    Args:
        network_id: The ID of the network.
        attr_types: Dict mapping attribute name to data_type ("float", "string", etc.).
        model_class: The SQLAlchemy model class for the attribute (NodeAttribute or EdgeAttribute).
        db: Database session.
        commit: Whether to commit the transaction.
        descriptions: Optional Dict mapping attribute name to description text.
        
    Returns:
        A dictionary mapping attribute names to their database IDs.
    """
    keys = set(attr_types.keys())
    if not keys: 
        return {}
    
    # Step 1: Bulk Insert (Ignore duplicates)
    values = [
        {
            "network_id": network_id,
            "attribute_name": key,
            "data_type": attr_types.get(key, "string"),
            "description": descriptions.get(key) if descriptions else None
        }
        for key in keys
    ]
    
    stmt = insert(model_class).values(values)
    
    # If conflict, updated description if provided to ensure it's captured
    update_dict = {}
    if descriptions:
        update_dict = {"description": stmt.excluded.description}

    if update_dict:
        stmt = stmt.on_conflict_do_update(
            index_elements=['network_id', 'attribute_name'],
            set_=update_dict
        )
    else:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['network_id', 'attribute_name']
        )
    
    db.execute(stmt)

    # Avoid extra commits when the caller wraps operations in a transaction
    if commit:
        db.commit()
    else:
        db.flush()
    
    # Step 2: Fetch all IDs (now guaranteed to exist)
    all_attrs = db.query(model_class).filter(
        model_class.network_id == network_id,
        model_class.attribute_name.in_(keys)
    ).all()
    
    return {attr.attribute_name: attr.id for attr in all_attrs}


def get_or_create_attribute(
    network_id: int, 
    name: str, 
    model_class: Type[models.Base], 
    db: Session, 
    data_type: str = "string"
) -> models.Base:
    """
    Get an existing attribute or create a new one if it doesn't exist.
    
    Args:
        network_id: The ID of the network.
        name: The name of the attribute.
        model_class: The model class (NodeAttribute or EdgeAttribute).
        db: Database session.
        data_type: The data type of the attribute.
        
    Returns:
        The attribute object.
    """
    attr = db.query(model_class).filter(
        model_class.network_id == network_id,
        model_class.attribute_name == name
    ).first()
    
    if not attr:
        attr = model_class(network_id=network_id, attribute_name=name, data_type=data_type)
        db.add(attr)
        db.commit()
        db.refresh(attr)
    return attr


def delete_attribute_values(
    network_id: int, 
    attribute_id: int, 
    model_val_class: Type[models.Base], 
    db: Session
) -> None:
    """
    Delete all attribute values for a specific attribute in a network.
    
    Args:
        network_id: The ID of the network (unused currently but kept for potential future scoping).
        attribute_id: The ID of the attribute definition.
        model_val_class: The model class for values (NodeAttributeValue or EdgeAttributeValue).
        db: Database session.
    """
    # Delete children first (safe approach)
    # Find IDs to delete
    subquery = db.query(model_val_class.id).filter(model_val_class.attribute_id == attribute_id)
    
    # Delete Float/Text values
    if model_val_class == models.NodeAttributeValue:
        db.query(models.NodeFloatAttributeValue).filter(
            models.NodeFloatAttributeValue.node_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)
        
        db.query(models.NodeTextAttributeValue).filter(
            models.NodeTextAttributeValue.node_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)
        
    elif model_val_class == models.EdgeAttributeValue:
        db.query(models.EdgeFloatAttributeValue).filter(
            models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)
        
        db.query(models.EdgeTextAttributeValue).filter(
            models.EdgeTextAttributeValue.edge_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)
        
    # Delete parent values
    db.query(model_val_class).filter(model_val_class.attribute_id == attribute_id).delete(synchronize_session=False)
    db.commit()


def get_attribute_stats(
    network_id: int, 
    model_attr: Type[models.Base], 
    model_val: Type[models.Base], 
    model_float: Type[models.Base], 
    model_text: Type[models.Base], 
    db: Session
) -> List[Dict[str, Any]]:
    """
    Fetch attributes with statistics to help LLM decide visualization types.
    
    Args:
        network_id: The ID of the network.
        model_attr: Attribute definition model (NodeAttribute/EdgeAttribute).
        model_val: Attribute value linking model (NodeAttributeValue/EdgeAttributeValue).
        model_float: Float value model.
        model_text: Text value model.
        db: Database session.
        
    Returns:
        List of dictionaries containing attribute metadata and statistics.
    """
    attributes = db.query(model_attr).filter(model_attr.network_id == network_id).all()
    result = []

    for attr in attributes:
        attr_data = {
            "name": attr.attribute_name,
            "data_type": attr.data_type,
            "description": attr.description
        }
        
        try:
            if attr.data_type == "float":
                # Get Min/Max
                # Determine join condition based on model type
                if model_val == models.NodeAttributeValue:
                    join_cond = (model_val.id == model_float.node_attribute_value_id)
                else:
                    join_cond = (model_val.id == model_float.edge_attribute_value_id)

                stats = db.query(
                    func.min(model_float.float_value),
                    func.max(model_float.float_value)
                ).join(model_val, join_cond)\
                .filter(model_val.attribute_id == attr.id).first()
                
                if stats and stats[0] is not None:
                    attr_data["stats"] = {
                        "min": float(stats[0]),
                        "max": float(stats[1])
                    }
            
            elif attr.data_type == "string":
                # Get unique count and top values
                if model_val == models.NodeAttributeValue:
                    join_cond = (model_val.id == model_text.node_attribute_value_id)
                else:
                    join_cond = (model_val.id == model_text.edge_attribute_value_id)

                # Unique Count
                unique_count = db.query(func.count(func.distinct(model_text.text_value)))\
                    .join(model_val, join_cond)\
                    .filter(model_val.attribute_id == attr.id).scalar()
                    
                # Top 10 unique values
                top_values = db.query(model_text.text_value, func.count(model_text.text_value).label('count'))\
                    .join(model_val, join_cond)\
                    .filter(model_val.attribute_id == attr.id)\
                    .group_by(model_text.text_value)\
                    .order_by(func.count(model_text.text_value).desc())\
                    .limit(10).all()
                    
                attr_data["stats"] = {
                    "unique_count": unique_count,
                    "top_values": [v[0] for v in top_values]
                }
        except Exception as e:
            # Fallback if calculation fails, just return name/type to avoid blocking response
            logger.error(f"Error calculating stats for {attr.attribute_name} in network {network_id}: {e}")
            pass

        result.append(attr_data)
        
    return result

def get_specific_attribute_stats(
    network_id: int, 
    attribute_name: str,
    model_attr: Type[models.Base], 
    model_val: Type[models.Base], 
    model_float: Type[models.Base], 
    model_text: Type[models.Base], 
    db: Session
) -> Optional[Dict[str, Any]]:
    """
    Fetch statistics for a SINGLE specific attribute.
    """
    attr = db.query(model_attr).filter(
        model_attr.network_id == network_id,
        model_attr.attribute_name == attribute_name
    ).first()
    
    if not attr:
        return None

    attr_data = {
        "name": attr.attribute_name,
        "data_type": attr.data_type,
        "description": attr.description
    }
    
    try:
        if attr.data_type == "float":
            if model_val == models.NodeAttributeValue:
                join_cond = (model_val.id == model_float.node_attribute_value_id)
            else:
                join_cond = (model_val.id == model_float.edge_attribute_value_id)

            stats = db.query(
                func.min(model_float.float_value),
                func.max(model_float.float_value)
            ).join(model_val, join_cond)\
            .filter(model_val.attribute_id == attr.id).first()
            
            if stats and stats[0] is not None:
                attr_data["stats"] = {
                    "min": float(stats[0]),
                    "max": float(stats[1])
                }
        
        elif attr.data_type == "string":
            if model_val == models.NodeAttributeValue:
                join_cond = (model_val.id == model_text.node_attribute_value_id)
            else:
                join_cond = (model_val.id == model_text.edge_attribute_value_id)

            unique_count = db.query(func.count(func.distinct(model_text.text_value)))\
                .join(model_val, join_cond)\
                .filter(model_val.attribute_id == attr.id).scalar()
                
            # For specific attribute text stats, we can return MORE top values (e.g. 20)
            top_values = db.query(model_text.text_value, func.count(model_text.text_value).label('count'))\
                .join(model_val, join_cond)\
                .filter(model_val.attribute_id == attr.id)\
                .group_by(model_text.text_value)\
                .order_by(func.count(model_text.text_value).desc())\
                .limit(20).all() # Higher limit for detailed inspection
                
            attr_data["stats"] = {
                "unique_count": unique_count,
                "top_values": [v[0] for v in top_values]
            }
    except Exception as e:
        logger.error(f"Error calculating stats for {attr.attribute_name} in network {network_id}: {e}")
        pass
        
    return attr_data
