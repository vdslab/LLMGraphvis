from sqlalchemy.orm import Session
from sqlalchemy import or_
from app import models
from app.core.logging import get_logger
from typing import List, Dict, Any, Optional

logger = get_logger(__name__)

def search_nodes(
    network_id: int, 
    query: str, 
    attribute_name: Optional[str] = None, 
    limit: int = 10, 
    db: Session = None
) -> List[Dict[str, Any]]:
    """
    Search for nodes in a network.
    
    Args:
        network_id: The ID of the network to search in.
        query: The search string.
        attribute_name: Optional. If provided, search only within this attribute's values.
                        If None, search against node_id and label.
        limit: Max number of results to return.
        db: Database session.
        
    Returns:
        List of dicts containing node info (id, node_id, label, and matched attribute if applicable).
    """
    logger.info(f"Searching nodes in network {network_id} (query='{query}', attr='{attribute_name}', limit={limit})")
    
    results = []
    
    if attribute_name:
        results = _search_by_attribute(db, network_id, query, attribute_name, limit)
    else:
        results = _search_default(db, network_id, query, limit)
            
    logger.info(f"Found {len(results)} matches")
    return results

def _search_by_attribute(db: Session, network_id: int, query: str, attribute_name: str, limit: int) -> List[Dict[str, Any]]:
    """
    Find matches in Text Attributes with the given name.
    """
    # Join: Node -> NodeAttributeValue -> NodeAttribute (filter name) -> NodeTextAttributeValue (filter value)
    q = db.query(models.Node, models.NodeTextAttributeValue.text_value)\
        .join(models.NodeAttributeValue, models.Node.id == models.NodeAttributeValue.node_id)\
        .join(models.NodeAttribute, models.NodeAttributeValue.attribute_id == models.NodeAttribute.id)\
        .join(models.NodeTextAttributeValue, models.NodeAttributeValue.id == models.NodeTextAttributeValue.node_attribute_value_id)\
        .filter(
            models.Node.network_id == network_id,
            models.NodeAttribute.attribute_name == attribute_name,
            models.NodeTextAttributeValue.text_value.ilike(f"%{query}%")
        )\
        .limit(limit)\
        .all()
        
    results = []
    for node, match_value in q:
        results.append({
            "id": node.node_id, # Return the string ID used in GraphML
            "label": node.label,
            "match": match_value,
            "score": 1.0 # Placeholder for ranking if needed
        })
    return results

def _search_default(db: Session, network_id: int, query: str, limit: int) -> List[Dict[str, Any]]:
    """
    Simple OR search on node_id and label.
    """
    q = db.query(models.Node)\
        .filter(
            models.Node.network_id == network_id,
            or_(
                models.Node.node_id.ilike(f"%{query}%"),
                models.Node.label.ilike(f"%{query}%")
            )
        )\
        .limit(limit)\
        .all()
        
    results = []
    for node in q:
        match_val = node.label if node.label and query.lower() in node.label.lower() else node.node_id
        results.append({
            "id": node.node_id,
            "label": node.label,
            "match": match_val,
            "score": 1.0
        })
    return results
