from sqlalchemy.orm import Session
from app import models

def generate_visualization_data(network_id: int, db: Session, layout_name="spring", node_size_config=None, node_color_config=None, edge_width_config=None, edge_color_config=None):
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    
    # --- Helper Functions ---
    
    def get_node_attr_value(node_id, attr_name):
        attr = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.attribute_name == attr_name
        ).first()
        if not attr: return None
        
        val = db.query(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.node_id == node_id,
            models.NodeAttributeValue.attribute_id == attr.id
        ).first()
        
        if val:
            if val.float_value: return val.float_value.float_value
            if val.text_value: return val.text_value.text_value
        return None

    def get_edge_attr_value(edge_id, attr_name):
        attr = db.query(models.EdgeAttribute).filter(
            models.EdgeAttribute.network_id == network_id,
            models.EdgeAttribute.attribute_name == attr_name
        ).first()
        if not attr: return None
        
        val = db.query(models.EdgeAttributeValue).filter(
            models.EdgeAttributeValue.edge_id == edge_id,
            models.EdgeAttributeValue.attribute_id == attr.id
        ).first()
        
        if val:
            if val.float_value:
                return val.float_value.float_value
            if val.text_value:
                return val.text_value.text_value
        return None

    def normalize(value, min_val, max_val, target_min, target_max):
        if max_val == min_val: return target_min
        return target_min + ((value - min_val) / (max_val - min_val)) * (target_max - target_min)

    def interpolate_color(val, min_val, max_val, start_color, end_color):
        # Simple linear interpolation for hex colors
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        def rgb_to_hex(rgb):
            return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

        if max_val == min_val: return start_color
        
        ratio = (val - min_val) / (max_val - min_val)
        ratio = max(0, min(1, ratio)) # Clamp
        
        s_rgb = hex_to_rgb(start_color)
        e_rgb = hex_to_rgb(end_color)
        
        new_rgb = (
            s_rgb[0] + (e_rgb[0] - s_rgb[0]) * ratio,
            s_rgb[1] + (e_rgb[1] - s_rgb[1]) * ratio,
            s_rgb[2] + (e_rgb[2] - s_rgb[2]) * ratio
        )
        return rgb_to_hex(new_rgb)

    # --- Pre-calculation for Normalization ---

    def get_attr_stats(config, model_attr, model_val, model_float_val):
        if not config: return None, 0, 0
        attr_name = config.get("attribute")
        attr_record = db.query(model_attr).filter(
            model_attr.network_id == network_id,
            model_attr.attribute_name == attr_name
        ).first()
        
        if not attr_record: return None, 0, 0
        
        values_map = {}
        min_val = float('inf')
        max_val = float('-inf')
        
        # Fetch all values for this attribute
        all_vals = db.query(model_val).filter(model_val.attribute_id == attr_record.id).all()
        
        for v in all_vals:
            val = None
            if v.float_value: val = v.float_value.float_value
            elif v.text_value: val = v.text_value.text_value # For categorical
            
            if val is not None:
                # Store ID mapping
                entity_id = v.node_id if model_val == models.NodeAttributeValue else v.edge_id
                values_map[entity_id] = val
                
                if isinstance(val, (int, float)):
                    if val < min_val: min_val = val
                    if val > max_val: max_val = val
                    
        return values_map, min_val, max_val

    # Node Stats
    node_size_map, node_size_min, node_size_max = get_attr_stats(
        node_size_config, models.NodeAttribute, models.NodeAttributeValue, models.NodeFloatAttributeValue
    )
    node_color_map, node_color_min, node_color_max = get_attr_stats(
        node_color_config, models.NodeAttribute, models.NodeAttributeValue, models.NodeFloatAttributeValue
    )
    
    # Edge Stats
    edge_width_map, edge_width_min, edge_width_max = get_attr_stats(
        edge_width_config, models.EdgeAttribute, models.EdgeAttributeValue, models.EdgeFloatAttributeValue
    )
    edge_color_map, edge_color_min, edge_color_max = get_attr_stats(
        edge_color_config, models.EdgeAttribute, models.EdgeAttributeValue, models.EdgeFloatAttributeValue
    )

    # --- Node Processing ---
    
    vis_nodes = []
    layout_x_attr = f"{layout_name}_x"
    layout_y_attr = f"{layout_name}_y"

    for n in nodes:
        # Defaults
        size = 20
        color = "#5384ED"
        
        # 1. Size
        if node_size_map and n.id in node_size_map:
            val = node_size_map[n.id]
            if isinstance(val, (int, float)):
                target_min = node_size_config.get("min", 20)
                target_max = node_size_config.get("max", 60)
                size = normalize(val, node_size_min, node_size_max, target_min, target_max)

        # 2. Color
        if node_color_map and n.id in node_color_map:
            val = node_color_map[n.id]
            scale_type = node_color_config.get("scale_type", "LINEAR")
            
            if scale_type == "LINEAR" and isinstance(val, (int, float)):
                gradient = node_color_config.get("gradient", ["#d1e0ff", "#003399"])
                color = interpolate_color(val, node_color_min, node_color_max, gradient[0], gradient[1])
            elif scale_type == "CATEGORICAL":
                color_map = node_color_config.get("color_map", {})
                # Try exact match first, then string match
                if str(val) in color_map:
                    color = color_map[str(val)]
                else:
                    # Fallback or cycle colors if needed (omitted for simplicity)
                    pass

        # 3. Layout
        x = get_node_attr_value(n.id, layout_x_attr)
        y = get_node_attr_value(n.id, layout_y_attr)
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
        
    # --- Edge Processing ---
    
    vis_edges = []
    for e in edges:
        source_node = db.query(models.Node).get(e.source_node_id)
        target_node = db.query(models.Node).get(e.target_node_id)
        
        # Defaults
        width = 1
        color = "#ccc"

        # 1. Width
        if edge_width_map and e.id in edge_width_map:
            val = edge_width_map[e.id]
            if isinstance(val, (int, float)):
                target_min = edge_width_config.get("min", 1)
                target_max = edge_width_config.get("max", 10)
                width = normalize(val, edge_width_min, edge_width_max, target_min, target_max)

        # 2. Color
        if edge_color_map and e.id in edge_color_map:
            val = edge_color_map[e.id]
            scale_type = edge_color_config.get("scale_type", "LINEAR")
            
            if scale_type == "LINEAR" and isinstance(val, (int, float)):
                gradient = edge_color_config.get("gradient", ["#eeeeee", "#000000"])
                color = interpolate_color(val, edge_color_min, edge_color_max, gradient[0], gradient[1])
            elif scale_type == "CATEGORICAL":
                color_map = edge_color_config.get("color_map", {})
                if str(val) in color_map:
                    color = color_map[str(val)]

        vis_edges.append({
            "source": source_node.node_id,
            "target": target_node.node_id,
            "width": width,
            "color": color
        })
        
    return {"nodes": vis_nodes, "links": vis_edges}
