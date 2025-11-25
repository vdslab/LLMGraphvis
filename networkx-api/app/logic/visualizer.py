from sqlalchemy.orm import Session
from app import models

def generate_visualization_data(network_id: int, db: Session, layout_name="spring", node_size_config=None, node_color_config=None, edge_width_config=None, edge_color_config=None):
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    
    # Helper to get attribute values
    # In a real app, we'd optimize this query
    def get_node_attr_value(node_id, attr_name):
        attr = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.attribute_name == attr_name
        ).first()
        if not attr:
            return None
        
        val = db.query(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.node_id == node_id,
            models.NodeAttributeValue.attribute_id == attr.id
        ).first()
        
        if val:
            if val.float_value:
                return val.float_value.float_value
            # Add text value check if needed
        return None

    def get_edge_attr_value(edge_id, attr_name):
        attr = db.query(models.EdgeAttribute).filter(
            models.EdgeAttribute.network_id == network_id,
            models.EdgeAttribute.attribute_name == attr_name
        ).first()
        if not attr:
            return None
        
        val = db.query(models.EdgeAttributeValue).filter(
            models.EdgeAttributeValue.edge_id == edge_id,
            models.EdgeAttributeValue.attribute_id == attr.id
        ).first()
        
        if val:
            if val.float_value:
                return val.float_value.float_value
            # Add text value check if needed
        return None

    vis_nodes = []
    
    # Pre-fetch layout attributes
    layout_x_attr = f"{layout_name}_x"
    layout_y_attr = f"{layout_name}_y"
    
    # Pre-calculate Node Size Min/Max if config exists
    node_size_map = {}
    node_size_min_val = 0
    node_size_max_val = 0
    has_node_size_data = False
    
    if node_size_config:
        attr_name = node_size_config.get("attribute")
        attr_record = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.attribute_name == attr_name
        ).first()
        
        if attr_record:
            values = db.query(models.NodeAttributeValue).filter(
                models.NodeAttributeValue.attribute_id == attr_record.id
            ).all()
            
            valid_values = []
            for v in values:
                if v.float_value is not None:
                    val = v.float_value.float_value
                    valid_values.append(val)
                    node_size_map[v.node_id] = val
            
            if valid_values:
                node_size_min_val = min(valid_values)
                node_size_max_val = max(valid_values)
                has_node_size_data = True

    for n in nodes:
        # Default visual props
        size = 20
        color = "#5384ED"
        
        # Apply Size Config
        if has_node_size_data:
            val = node_size_map.get(n.id)
            if val is not None:
                target_min_size = node_size_config.get("min", 20)
                target_max_size = node_size_config.get("max", 60)
                
                if node_size_max_val == node_size_min_val:
                    size = target_min_size
                else:
                    norm_val = (val - node_size_min_val) / (node_size_max_val - node_size_min_val)
                    size = target_min_size + (norm_val * (target_max_size - target_min_size))
                
        # Apply Color Config
        if node_color_config:
            # Simplified color mapping
            pass

        # Fetch Layout Coordinates
        x = get_node_attr_value(n.id, layout_x_attr)
        y = get_node_attr_value(n.id, layout_y_attr)
        
        # Default to center if not found (should not happen if initialized correctly)
        if x is None: x = 0.5
        if y is None: y = 0.5

        vis_nodes.append({
            "id": n.node_id,
            "label": n.label,
            "x": x,
            "y": y,
            "size": size, 
            "color": color 
        })
        
    vis_edges = []
    for e in edges:
        # Need to resolve source/target node_ids to string IDs for frontend D3
        source_node = db.query(models.Node).get(e.source_node_id)
        target_node = db.query(models.Node).get(e.target_node_id)
        
        width = 5
        color = "#ccc"

        # Apply Edge Width Config
        if edge_width_config:
            attr_name = edge_width_config.get("attribute")
            val = get_edge_attr_value(e.id, attr_name)
            if val is not None:
                min_width = edge_width_config.get("min", 5)
                max_width = edge_width_config.get("max", 10)
                # Simplified scaling, assuming val is roughly normalized or small
                # In production, we should normalize against min/max of the dataset
                width = min_width + (val * 0.5) # Arbitrary scaling for now
                if width > max_width: width = max_width

        vis_edges.append({
            "source": source_node.node_id,
            "target": target_node.node_id,
            "width": width,
            "color": color
        })
        
    return {"nodes": vis_nodes, "links": vis_edges}
