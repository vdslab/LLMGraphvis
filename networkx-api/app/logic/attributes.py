from sqlalchemy.orm import Session
from app import models
from typing import Dict, List, Any

# --- Attributes Helper Functions ---

def _clear_network_data(network_id: int, db: Session):
    """
    Clears all graph data (nodes, edges, attribute values) for a network.
    Does NOT delete the Network record itself or Attribute Definitions (to preserve schema if reused).
    """
    # 1. Delete Edge Attribute Values (and their children)
    # Get all EdgeAttributeValue IDs for this network
    eav_ids = [r[0] for r in db.query(models.EdgeAttributeValue.id).join(models.Edge).filter(models.Edge.network_id == network_id).all()]
    
    if eav_ids:
        db.query(models.EdgeFloatAttributeValue).filter(models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(eav_ids)).delete(synchronize_session=False)
        db.query(models.EdgeTextAttributeValue).filter(models.EdgeTextAttributeValue.edge_attribute_value_id.in_(eav_ids)).delete(synchronize_session=False)
        db.query(models.EdgeAttributeValue).filter(models.EdgeAttributeValue.id.in_(eav_ids)).delete(synchronize_session=False)

    # 2. Delete Node Attribute Values (and their children)
    # Get all NodeAttributeValue IDs
    nav_ids = [r[0] for r in db.query(models.NodeAttributeValue.id).join(models.Node).filter(models.Node.network_id == network_id).all()]
    
    if nav_ids:
        db.query(models.NodeFloatAttributeValue).filter(models.NodeFloatAttributeValue.node_attribute_value_id.in_(nav_ids)).delete(synchronize_session=False)
        db.query(models.NodeTextAttributeValue).filter(models.NodeTextAttributeValue.node_attribute_value_id.in_(nav_ids)).delete(synchronize_session=False)
        db.query(models.NodeAttributeValue).filter(models.NodeAttributeValue.id.in_(nav_ids)).delete(synchronize_session=False)

    # 3. Delete Edges
    db.query(models.Edge).filter(models.Edge.network_id == network_id).delete(synchronize_session=False)

    # 4. Delete Nodes
    db.query(models.Node).filter(models.Node.network_id == network_id).delete(synchronize_session=False)
    
    db.commit()

def _ensure_attributes(network_id: int, attr_types: Dict[str, str], model_class, db: Session, commit: bool = True, descriptions: Dict[str, str] = None) -> Dict[str, int]:
    """
    Ensure attributes exist for the given keys and return a map of {name: id}.
    attr_types: Dict mapping attribute name to data_type ("float", "string", etc.)
    descriptions: Optional Dict mapping attribute name to description text.
    """
    keys = set(attr_types.keys())
    if not keys: return {}
    
    from sqlalchemy.dialects.postgresql import insert
    
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
    
    # If conflict, we might want to update the description if it's new?
    # For now, let's just do ON CONFLICT UPDATE description if provided.
    # This ensures we capture the description even if attribute existed.
    
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

def _get_or_create_attribute(network_id: int, name: str, model_class, db: Session, data_type: str = "string"):
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

def _delete_attribute_values(network_id: int, attribute_id: int, model_val_class, db: Session):
    """
    Delete all attribute values for a specific attribute in a network.
    """
    # Delete children first (safe approach)
    # Find IDs to delete
    subquery = db.query(model_val_class.id).filter(model_val_class.attribute_id == attribute_id)
    
    # Delete Float/Text values
    if model_val_class == models.NodeAttributeValue:
        db.query(models.NodeFloatAttributeValue).filter(models.NodeFloatAttributeValue.node_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
        db.query(models.NodeTextAttributeValue).filter(models.NodeTextAttributeValue.node_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
    elif model_val_class == models.EdgeAttributeValue:
        db.query(models.EdgeFloatAttributeValue).filter(models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
        db.query(models.EdgeTextAttributeValue).filter(models.EdgeTextAttributeValue.edge_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
        
    # Delete parent values
    db.query(model_val_class).filter(model_val_class.attribute_id == attribute_id).delete(synchronize_session=False)
    db.commit()

from sqlalchemy import func

def get_attribute_stats(network_id: int, model_attr, model_val, model_float, model_text, db: Session) -> List[Dict[str, Any]]:
    """
    Fetch attributes with statistics to help LLM decide visualization types.
    """
    attributes = db.query(model_attr).filter(model_attr.network_id == network_id).all()
    result = []

    for attr in attributes:
        attr_data = {
            "name": attr.attribute_name,
            "data_type": attr.data_type,
            "description": attr.description  # Added description
        }
        
        try:
            if attr.data_type == "float":
                # Get Min/Max
                stats = db.query(
                    func.min(model_float.float_value),
                    func.max(model_float.float_value)
                ).join(model_val, model_val.id == model_float.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_float.edge_attribute_value_id)\
                .filter(model_val.attribute_id == attr.id).first()
                
                if stats and stats[0] is not None:
                    attr_data["stats"] = {
                        "min": float(stats[0]),
                        "max": float(stats[1])
                    }
            
            elif attr.data_type == "string":
                # Get unique count and top values
                # Unique Count
                unique_count = db.query(func.count(func.distinct(model_text.text_value)))\
                    .join(model_val, model_val.id == model_text.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_text.edge_attribute_value_id)\
                    .filter(model_val.attribute_id == attr.id).scalar()
                    
                # Top 10 unique values
                top_values = db.query(model_text.text_value, func.count(model_text.text_value).label('count'))\
                    .join(model_val, model_val.id == model_text.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_text.edge_attribute_value_id)\
                    .filter(model_val.attribute_id == attr.id)\
                    .group_by(model_text.text_value)\
                    .order_by(func.count(model_text.text_value).desc())\
                    .limit(10).all()
                    
                attr_data["stats"] = {
                    "unique_count": unique_count,
                    "top_values": [v[0] for v in top_values]
                }
        except Exception as e:
            # Fallback if calculation fails, just return name/type
            print(f"Error calculating stats for {attr.attribute_name}: {e}")
            pass

        result.append(attr_data)
        
    return result
