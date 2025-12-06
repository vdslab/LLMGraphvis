from sqlalchemy.orm import Session
from app import models
from app.logic import utils
from typing import Dict, Any, List, Set

def generate_visualization_data(
    network_id: int, 
    db: Session, 
    layout_name="spring", 
    node_size_config=None, 
    node_color_config=None, 
    edge_width_config=None, 
    edge_color_config=None, 
    focus_network_id=None, 
    context_config=None, 
    focus_config=None,
    custom_node_colors=None,
    node_label_config=None
):
    # --- Helper Functions ---
    def collect_required_attrs(config, attr_set):
        if config and config.get("attribute"):
            attr_set.add(config["attribute"])

    def fetch_attr_map(net_id, attr_names, model):
        if not attr_names: return {}
        defs = db.query(model).filter(
            model.network_id == net_id,
            model.attribute_name.in_(attr_names)
        ).all()
        return {attr.attribute_name: attr.id for attr in defs}

    def get_val(entity_id, attr_name, attr_map, values_map):
        if attr_name not in attr_map: return None
        attr_id = attr_map[attr_name]
        if entity_id in values_map and attr_id in values_map[entity_id]:
            return values_map[entity_id][attr_id]
        return None

    def calculate_stats(config, attr_map, values_map):
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

    # --- 1. Identify Required Attributes (Global & Focus) ---
    global_node_attrs = {f"{layout_name}_x", f"{layout_name}_y"}
    collect_required_attrs(node_size_config, global_node_attrs)
    collect_required_attrs(node_color_config, global_node_attrs)
    collect_required_attrs(node_label_config, global_node_attrs)

    focus_node_attrs = set()
    if focus_config:
        collect_required_attrs(focus_config.get("node_size_config"), focus_node_attrs)
        collect_required_attrs(focus_config.get("node_color_config"), focus_node_attrs)

    required_edge_attrs = set()
    collect_required_attrs(edge_width_config, required_edge_attrs)
    collect_required_attrs(edge_color_config, required_edge_attrs)

    # --- 2. Fetch Attribute Definitions ---
    # Global attributes (from network_id)
    global_node_attr_map = fetch_attr_map(network_id, global_node_attrs, models.NodeAttribute)
    edge_attr_map = fetch_attr_map(network_id, required_edge_attrs, models.EdgeAttribute)

    # Focus attributes (from focus_network_id)
    focus_node_attr_map = {}
    if focus_network_id and focus_node_attrs:
        focus_node_attr_map = fetch_attr_map(focus_network_id, focus_node_attrs, models.NodeAttribute)

    # --- 3. Fetch Attribute Values ---
    # We need values for ALL nodes in the main network for global attributes
    global_node_values = _fetch_attribute_values(db, models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, list(global_node_attr_map.values()))
    edge_values = _fetch_attribute_values(db, models.EdgeAttributeValue, models.EdgeFloatAttributeValue, models.EdgeTextAttributeValue, list(edge_attr_map.values()))

    # We need values for FOCUS nodes for focus attributes
    focus_node_values = {}
    focus_node_map = {} # node_id_str -> db_id (in focus network)
    
    if focus_network_id:
        # Fetch all nodes in focus network to build the map
        focus_nodes = db.query(models.Node).filter(models.Node.network_id == focus_network_id).all()
        focus_node_map = {n.node_id: n.id for n in focus_nodes}
        
        if focus_node_attr_map:
            # Fetch values for these nodes
            # Optimization: We could filter by node IDs, but _fetch_attribute_values filters by attribute IDs which is efficient enough if attributes are specific to network
            focus_node_values = _fetch_attribute_values(db, models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, list(focus_node_attr_map.values()))

    # --- 4. Calculate Stats ---
    # Global Stats
    node_size_stats = calculate_stats(node_size_config, global_node_attr_map, global_node_values)
    node_color_stats = calculate_stats(node_color_config, global_node_attr_map, global_node_values)
    edge_width_stats = calculate_stats(edge_width_config, edge_attr_map, edge_values)
    edge_color_stats = calculate_stats(edge_color_config, edge_attr_map, edge_values)

    # Focus Stats
    focus_node_size_stats = (None, 0, 0)
    focus_node_color_stats = (None, 0, 0)
    if focus_config:
        focus_node_size_stats = calculate_stats(focus_config.get("node_size_config"), focus_node_attr_map, focus_node_values)
        focus_node_color_stats = calculate_stats(focus_config.get("node_color_config"), focus_node_attr_map, focus_node_values)

    # --- 5. Build Visualization Data ---
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    smart_defaults = utils.calculate_smart_node_size(len(nodes))
    
    # Identify Focus Nodes (using string ID set for fast lookup)
    focus_node_ids_str = set(focus_node_map.keys())

    vis_nodes = []
    
    # Pre-calculate Ranking/Custom Color Maps (Global)
    ranking_color_map = {}
    if node_color_config and node_color_config.get("scale_type") == "RANKING":
        attr_name = node_color_config.get("attribute")
        if attr_name in global_node_attr_map:
            attr_id = global_node_attr_map[attr_name]
            values_list = []
            for nid, attrs in global_node_values.items():
                if attr_id in attrs:
                    val = attrs[attr_id]
                    if isinstance(val, (int, float)):
                        values_list.append((nid, val))
            values_list.sort(key=lambda x: x[1], reverse=True)
            rules = node_color_config.get("ranking_rules", [])
            current_idx = 0
            for rule in rules:
                count = rule.get("top", 0)
                color = rule.get("color", "#999999")
                end_idx = min(current_idx + count, len(values_list))
                for i in range(current_idx, end_idx):
                    nid = values_list[i][0]
                    ranking_color_map[nid] = color
                current_idx = end_idx
                if current_idx >= len(values_list): break

    custom_color_map = {}
    if custom_node_colors:
        for item in custom_node_colors:
            if "node_id" in item and "color" in item:
                custom_color_map[str(item["node_id"])] = item["color"]

    layout_x_attr = f"{layout_name}_x"
    layout_y_attr = f"{layout_name}_y"

    for n in nodes:
        # Determine if node is in focus
        is_focused = n.node_id in focus_node_ids_str
        
        # --- Visibility Check ---
        if not is_focused and context_config and context_config.get("visible") is False:
            continue # Skip rendering this node

        # --- Base Attributes (Global) ---
        size = smart_defaults["default"]
        color = "#5384ED"
        opacity = 1.0
        
        # Global Size
        if node_size_stats[0]:
            val = get_val(n.id, node_size_config["attribute"], global_node_attr_map, global_node_values)
            if isinstance(val, (int, float)):
                target_min = node_size_config.get("min", smart_defaults["min"])
                target_max = node_size_config.get("max", smart_defaults["max"])
                size = utils.normalize(val, node_size_stats[1], node_size_stats[2], target_min, target_max)

        # Global Color
        specific_color = None
        if str(n.node_id) in custom_color_map:
            specific_color = custom_color_map[str(n.node_id)]
        
        if not specific_color and node_color_config and node_color_stats[0]:
            attr_name = node_color_config.get("attribute")
            scale_type = node_color_config.get("scale_type", "LINEAR")
            val = get_val(n.id, attr_name, global_node_attr_map, global_node_values)
            
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

        if specific_color:
            color = specific_color
        else:
            color = node_color_config.get("default_color", "#5384ED") if node_color_config else "#5384ED"

        # --- Focus/Context Overrides ---
        if focus_network_id:
            if is_focused:
                # Apply Focus Config Overrides
                if focus_config:
                    # Get the DB ID of this node in the focus network
                    focus_db_id = focus_node_map.get(n.node_id)
                    
                    if focus_db_id:
                        # Focus Size
                        f_size_conf = focus_config.get("node_size_config")
                        if f_size_conf and focus_node_size_stats[0]:
                            val = get_val(focus_db_id, f_size_conf["attribute"], focus_node_attr_map, focus_node_values)
                            if isinstance(val, (int, float)):
                                target_min = f_size_conf.get("min", smart_defaults["min"])
                                target_max = f_size_conf.get("max", smart_defaults["max"])
                                size = utils.normalize(val, focus_node_size_stats[1], focus_node_size_stats[2], target_min, target_max)

                        # Focus Color
                        f_color_conf = focus_config.get("node_color_config")
                        if f_color_conf:
                            if f_color_conf.get("static_color"):
                                color = f_color_conf["static_color"]
                            elif focus_node_color_stats[0]:
                                attr_name = f_color_conf.get("attribute")
                                scale_type = f_color_conf.get("scale_type", "LINEAR")
                                val = get_val(focus_db_id, attr_name, focus_node_attr_map, focus_node_values)
                                
                                if scale_type == "LINEAR" and isinstance(val, (int, float)):
                                    gradient = f_color_conf.get("gradient", ["#d1e0ff", "#003399"])
                                    color = utils.interpolate_color(val, focus_node_color_stats[1], focus_node_color_stats[2], gradient[0], gradient[1])
                                elif scale_type == "CATEGORICAL":
                                    color_map = f_color_conf.get("color_map", {})
                                    if str(val) in color_map:
                                        color = color_map[str(val)]

            else:
                # Apply Context Config
                if context_config:
                    opacity = context_config.get("opacity", 0.1)
                    if context_config.get("color"):
                        color = context_config["color"]
                    
                    if context_config.get("size"):
                        size = context_config["size"]
                    elif not node_size_stats[0]:
                        # If no global sizing is active, default context nodes to minimum size
                        size = smart_defaults["min"]

        # --- Layout ---
        x = get_val(n.id, layout_x_attr, global_node_attr_map, global_node_values)
        y = get_val(n.id, layout_y_attr, global_node_attr_map, global_node_values)
        if x is None: x = 0.5
        if y is None: y = 0.5

        # --- Label Selection ---
        label = n.label
        if node_label_config and node_label_config.get("attribute"):
            val = get_val(n.id, node_label_config["attribute"], global_node_attr_map, global_node_values)
            if val is not None:
                label = str(val)
        
        if not label:
            label = n.node_id

        vis_nodes.append({
            "id": n.node_id,
            "label": label,
            "x": x,
            "y": y,
            "size": size, 
            "color": color,
            "opacity": opacity
        })

    # --- Edges ---
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    smart_edge_defaults = utils.calculate_smart_edge_width(len(edges))
    vis_edges = []
    
    node_lookup = {n.id: n for n in nodes}

    for e in edges:
        source_node = node_lookup.get(e.source_node_id)
        target_node = node_lookup.get(e.target_node_id)
        
        if not source_node or not target_node:
            continue
        
        # Determine if edge is in focus (both source and target must be in focus)
        is_focused = False
        if focus_network_id:
            is_focused = (source_node.node_id in focus_node_ids_str) and (target_node.node_id in focus_node_ids_str)

        if not is_focused and context_config and context_config.get("visible") is False:
            continue

        width = smart_edge_defaults["default"]
        color = "#999"
        opacity = 1.0

        # Global Width/Color
        if edge_width_stats[0]:
            val = get_val(e.id, edge_width_config["attribute"], edge_attr_map, edge_values)
            if isinstance(val, (int, float)):
                target_min = edge_width_config.get("min", smart_edge_defaults["min"])
                target_max = edge_width_config.get("max", smart_edge_defaults["max"])
                width = utils.normalize(val, edge_width_stats[1], edge_width_stats[2], target_min, target_max)

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

        # Focus/Context Overrides
        if focus_network_id:
            if is_focused:
                # Focus overrides (if any)
                # Currently we only support node focus config in detail, but edge focus config could be added similarly.
                # For now, just highlight if context is dimmed.
                pass 
            else:
                if context_config:
                    opacity = context_config.get("opacity", 0.1)
                    if context_config.get("color"):
                        color = context_config["color"]

        vis_edges.append({
            "source": source_node.node_id,
            "target": target_node.node_id,
            "width": width,
            "color": color,
            "opacity": opacity
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
