from sqlalchemy.orm import Session
from app import models
from app.logic import utils
from typing import Dict, Any, List, Set

def generate_visualization_data(network_id: int, db: Session, layout_name="spring", node_size_config=None, node_color_config=None, edge_width_config=None, edge_color_config=None, overlay_network_id=None, overlay_config=None, custom_node_colors=None):
    # 1. Identify required attributes
    required_node_attrs = {f"{layout_name}_x", f"{layout_name}_y"}
    if node_size_config and node_size_config.get("attribute"):
        required_node_attrs.add(node_size_config["attribute"])
    if node_color_config and node_color_config.get("attribute"):
        required_node_attrs.add(node_color_config["attribute"])
        
    required_edge_attrs = set()
    if edge_width_config and edge_width_config.get("attribute"):
        required_edge_attrs.add(edge_width_config["attribute"])
    if edge_color_config and edge_color_config.get("attribute"):
        required_edge_attrs.add(edge_color_config["attribute"])

    # 2. Fetch Attribute Definitions (Name -> ID)
    node_attr_defs = db.query(models.NodeAttribute).filter(
        models.NodeAttribute.network_id == network_id,
        models.NodeAttribute.attribute_name.in_(required_node_attrs)
    ).all()
    node_attr_map = {attr.attribute_name: attr.id for attr in node_attr_defs}
    
    edge_attr_defs = db.query(models.EdgeAttribute).filter(
        models.EdgeAttribute.network_id == network_id,
        models.EdgeAttribute.attribute_name.in_(required_edge_attrs)
    ).all()
    edge_attr_map = {attr.attribute_name: attr.id for attr in edge_attr_defs}

    # 3. Fetch Attribute Values (Bulk)
    # We want a map: values[entity_id][attr_name] = value
    
    node_values = _fetch_attribute_values(db, models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, list(node_attr_map.values()))
    edge_values = _fetch_attribute_values(db, models.EdgeAttributeValue, models.EdgeFloatAttributeValue, models.EdgeTextAttributeValue, list(edge_attr_map.values()))

    # Helper to get value from our map
    def get_val(entity_id, attr_name, attr_map, values_map):
        if attr_name not in attr_map: return None
        attr_id = attr_map[attr_name]
        if entity_id in values_map and attr_id in values_map[entity_id]:
            return values_map[entity_id][attr_id]
        return None

    # 4. Calculate Stats for Normalization (Min/Max)
    # We can do this from the fetched values in memory
    def get_stats(config, attr_map, values_map):
        if not config or not config.get("attribute"): return None, 0, 0
        attr_name = config["attribute"]
        if attr_name not in attr_map: return None, 0, 0
        
        attr_id = attr_map[attr_name]
        vals = []
        for entity_vals in values_map.values():
            if attr_id in entity_vals:
                v = entity_vals[attr_id]
                if isinstance(v, (int, float)):
                    vals.append(v)
        
        if not vals: return None, 0, 0
        return True, min(vals), max(vals)

    node_size_stats = get_stats(node_size_config, node_attr_map, node_values)
    node_color_stats = get_stats(node_color_config, node_attr_map, node_values)
    edge_width_stats = get_stats(edge_width_config, edge_attr_map, edge_values)
    edge_color_stats = get_stats(edge_color_config, edge_attr_map, edge_values)

    # 5. Build Visualization Data
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    smart_defaults = utils.calculate_smart_node_size(len(nodes))
    
    # Overlay Logic: Fetch subgraph nodes if overlay_network_id is provided
    overlay_node_ids = set()
    if overlay_network_id:
        overlay_nodes = db.query(models.Node.node_id).filter(models.Node.network_id == overlay_network_id).all()
        overlay_node_ids = {n.node_id for n in overlay_nodes}
    
    vis_nodes = []
    
    # Pre-calculate Ranking Color Map if needed
    ranking_color_map = {}
    if node_color_config and node_color_config.get("scale_type") == "RANKING":
        attr_name = node_color_config.get("attribute")
        if attr_name in node_attr_map:
            attr_id = node_attr_map[attr_name]
            # Collect all values: (node_id, value)
            # node_values is {node_id: {attr_id: val}}
            values_list = []
            for nid, attrs in node_values.items():
                if attr_id in attrs:
                    val = attrs[attr_id]
                    if isinstance(val, (int, float)):
                        values_list.append((nid, val))
            
            # Sort descending
            values_list.sort(key=lambda x: x[1], reverse=True)
            
            # Apply rules
            rules = node_color_config.get("ranking_rules", [])
            current_idx = 0
            for rule in rules:
                count = rule.get("top", 0)
                color = rule.get("color", "#999999")
                
                # Assign color to the next 'count' nodes
                end_idx = min(current_idx + count, len(values_list))
                for i in range(current_idx, end_idx):
                    nid = values_list[i][0]
                    ranking_color_map[nid] = color
                
                current_idx = end_idx
                if current_idx >= len(values_list):
                    break

    
    # Pre-calculate Custom Color Map
    custom_color_map = {}
    if custom_node_colors:
        for item in custom_node_colors:
            if "node_id" in item and "color" in item:
                custom_color_map[item["node_id"]] = item["color"]

    layout_x_attr = f"{layout_name}_x"
    layout_y_attr = f"{layout_name}_y"

    for n in nodes:
        # Defaults
        size = smart_defaults["default"]
        color = "#5384ED"
        
        # Size
        if node_size_stats[0]:
            val = get_val(n.id, node_size_config["attribute"], node_attr_map, node_values)
            if isinstance(val, (int, float)):
                target_min = node_size_config.get("min", smart_defaults["min"])
                target_max = node_size_config.get("max", smart_defaults["max"])
                size = utils.normalize(val, node_size_stats[1], node_size_stats[2], target_min, target_max)

        # Color
        # 4. Determine Color
        specific_color = None
        
        # Priority 1: Custom Node Colors (Direct Override)
        # custom_color_map keys are Original IDs (node_id), not DB IDs (id)
        if n.node_id in custom_color_map:
            specific_color = custom_color_map[n.node_id]
        
        # Priority 2: Config-based (Ranking, Categorical, Linear)
        if not specific_color and node_color_config and node_color_stats[0]: # Check if config exists and has valid stats
            attr_name = node_color_config.get("attribute")
            scale_type = node_color_config.get("scale_type", "LINEAR") # Default was LINEAR
            
            val = None
            if attr_name in node_attr_map:
                attr_id = node_attr_map[attr_name]
                if attr_id in node_values.get(n.id, {}):
                    val = node_values[n.id][attr_id]
            
            if scale_type == "LINEAR" and isinstance(val, (int, float)):
                gradient = node_color_config.get("gradient", ["#d1e0ff", "#003399"])
                specific_color = utils.interpolate_color(val, node_color_stats[1], node_color_stats[2], gradient[0], gradient[1])
            elif scale_type == "CATEGORICAL":
                color_map = node_color_config.get("color_map", {})
                if str(val) in color_map:
                    specific_color = color_map[str(val)]
            elif scale_type == "RANKING":
                if n.id in ranking_color_map:
                    specific_color = ranking_color_map[n.id]

        # Apply Logic
        if overlay_network_id:
            if n.node_id in overlay_node_ids:
                # Inside Overlay
                if specific_color:
                    color = specific_color
                else:
                    color = overlay_config.get("highlight_color", "#FF4500") if overlay_config else "#FF4500"
            else:
                # Outside Overlay
                color = overlay_config.get("dimmed_color", "#B0B0B0") if overlay_config else "#B0B0B0"
        else:
            # No Overlay
            if specific_color:
                color = specific_color
            else:
                # If no specific color was determined, use a default.
                # The original code used "#5384ED" as a general default,
                # and node_color_config.get("default_color", "#B0B0B0") for RANKING if not found.
                # Let's use the general default if no config, or config's default if present.
                color = node_color_config.get("default_color", "#5384ED") if node_color_config else "#5384ED"

        # Layout
        x = get_val(n.id, layout_x_attr, node_attr_map, node_values)
        y = get_val(n.id, layout_y_attr, node_attr_map, node_values)
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

    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    smart_edge_defaults = utils.calculate_smart_edge_width(len(edges))
    vis_edges = []
    
    for e in edges:
        source_node = db.query(models.Node).get(e.source_node_id) # This is still N+1 if not careful, but usually cached by identity map if nodes loaded
        target_node = db.query(models.Node).get(e.target_node_id)
        
        # Optimization: We loaded all nodes above. SQLAlchemy Identity Map should handle this.
        # But to be safe, we can build a map of id->node_id_str
        # Let's trust Identity Map for now as we just queried them.
        
        # Defaults
        width = smart_edge_defaults["default"]
        color = "#999"

        # Width
        if edge_width_stats[0]:
            val = get_val(e.id, edge_width_config["attribute"], edge_attr_map, edge_values)
            if isinstance(val, (int, float)):
                target_min = edge_width_config.get("min", smart_edge_defaults["min"])
                target_max = edge_width_config.get("max", smart_edge_defaults["max"])
                width = utils.normalize(val, edge_width_stats[1], edge_width_stats[2], target_min, target_max)

        # Color
        if edge_color_stats[0]:
            val = get_val(e.id, edge_color_config["attribute"], edge_attr_map, edge_values)
            scale_type = edge_color_config.get("scale_type", "LINEAR")
            
            if scale_type == "LINEAR" and isinstance(val, (int, float)):
                gradient = edge_color_config.get("gradient", ["#eeeeee", "#000000"])
                color = utils.interpolate_color(val, edge_color_stats[1], edge_color_stats[2], gradient[0], gradient[1])
            elif scale_type == "CATEGORICAL":
                color_map = edge_color_config.get("color_map", {})
                if str(val) in color_map:
                    color = color_map[str(val)]
        
        # Overlay Override
        if overlay_network_id:
            if source_node.node_id in overlay_node_ids and target_node.node_id in overlay_node_ids:
                color = overlay_config.get("highlight_color", "#FF4500") if overlay_config else "#FF4500"
                width = width * 1.5 # Thicker
            else:
                color = overlay_config.get("dimmed_color", "#B0B0B0") if overlay_config else "#B0B0B0"
                width = 0.5 # Thinner

        vis_edges.append({
            "source": source_node.node_id,
            "target": target_node.node_id,
            "width": width,
            "color": color
        })

    return {"nodes": vis_nodes, "links": vis_edges}

def _fetch_attribute_values(db: Session, model_val, model_float, model_text, attr_ids: List[int]) -> Dict[int, Dict[int, Any]]:
    """
    Fetch all values for given attribute IDs and return a map: entity_id -> {attr_id: value}
    """
    if not attr_ids: return {}
    
    # Fetch base values
    # We need to join to get the actual values
    # This query fetches everything in one go
    
    # Construct query for Float values
    q_float = db.query(model_val.node_id if model_val == models.NodeAttributeValue else model_val.edge_id, model_val.attribute_id, model_float.float_value)\
        .join(model_float, model_val.id == model_float.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_float.edge_attribute_value_id)\
        .filter(model_val.attribute_id.in_(attr_ids)).all()

    # Construct query for Text values
    q_text = db.query(model_val.node_id if model_val == models.NodeAttributeValue else model_val.edge_id, model_val.attribute_id, model_text.text_value)\
        .join(model_text, model_val.id == model_text.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_text.edge_attribute_value_id)\
        .filter(model_val.attribute_id.in_(attr_ids)).all()

    result = {}
    
    for entity_id, attr_id, val in q_float:
        if entity_id not in result: result[entity_id] = {}
        result[entity_id][attr_id] = val
        
    for entity_id, attr_id, val in q_text:
        if entity_id not in result: result[entity_id] = {}
        result[entity_id][attr_id] = val
        
    return result
