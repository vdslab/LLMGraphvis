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

def _ensure_attributes(network_id: int, attr_types: Dict[str, str], model_class, db: Session, commit: bool = True) -> Dict[str, int]:
    """
    Ensure attributes exist for the given keys and return a map of {name: id}.
    attr_types: Dict mapping attribute name to data_type ("float", "string", etc.)
    """
    keys = set(attr_types.keys())
    if not keys: return {}
    
    from sqlalchemy.dialects.postgresql import insert
    
    # We want to identify IDs for both existing and newly created attributes.
    # Approach:
    # 1. Try to fetch all existing first (fast read).
    # 2. Insert missing ones.
    # 3. Fetch again (or assume we have them).
    # OR better: Upsert-like flow. 
    # But since we just need the map, let's do:
    # 1. Bulk Insert with ON CONFLICT DO NOTHING.
    # 2. Select all matching (network_id, keys).
    
    # Step 1: Prepare data for missing or existing check
    # Note: bulk_insert_mappings doesn't support ON CONFLICT easily in generic SQLAlchemy w/o native dialect usage.
    # Let's use dialect specific insert.
    
    values = [
        {
            "network_id": network_id,
            "attribute_name": key,
            "data_type": attr_types.get(key, "string")
        }
        for key in keys
    ]
    
    stmt = insert(model_class).values(values)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=['network_id', 'attribute_name'] # Constraint name usage is safer if known, but index elements work for unique constraints
    )
    
    db.execute(stmt)

    # Avoid extra commits when the caller wraps operations in a transaction
    if commit:
        db.commit()
    else:
        db.flush()
    
    # Step 2: Fetch all IDs (now guaranteed to exist)
    # We could try to use RETURNING but ON CONFLICT DO NOTHING returns nothing for existing rows.
    # So a simple SELECT after ensure is efficient enough here since metadata count is low (<< nodes/edges).
    
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
