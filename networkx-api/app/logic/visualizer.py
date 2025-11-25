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
    
    for n in nodes:
        # Default visual props
        size = 5
        color = "#5384ED"
        
        # Apply Size Config
        if node_size_config:
            attr_name = node_size_config.get("attribute")
            val = get_node_attr_value(n.id, attr_name)
            if val is not None:
                # Linear scale mapping
                min_size = node_size_config.get("min", 5)
                max_size = node_size_config.get("max", 20)
                # We need min/max of the attribute to scale properly
                # Simplified: assume 0-1 for centrality or just multiply
                # Better: Fetch min/max of attribute from DB
                size = min_size + (val * (max_size - min_size)) # Assuming val is 0-1
                
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
        
        width = 1
        color = "#ccc"

        # Apply Edge Width Config
        if edge_width_config:
            attr_name = edge_width_config.get("attribute")
            val = get_edge_attr_value(e.id, attr_name)
            if val is not None:
                min_width = edge_width_config.get("min", 1)
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
