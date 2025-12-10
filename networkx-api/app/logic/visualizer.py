from sqlalchemy.orm import Session
from app import models
from app.logic import utils
from app.logic.style_service import StyleService
from typing import Dict, Any, List, Set, Tuple

def generate_visualization_data(
    network_id: int, 
    db: Session, 
    layout_name="forceatlas2", 
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
    # --- 1. Identify Required Attributes ---
    global_attrs_configs = [node_size_config, node_color_config, node_label_config]
    global_node_attrs = StyleService.collect_required_attributes(global_attrs_configs)
    
    # Layout attributes are strictly required
    layout_x_attr = f"{layout_name}_x"
    layout_y_attr = f"{layout_name}_y"
    global_node_attrs.add(layout_x_attr)
    global_node_attrs.add(layout_y_attr)
    
    edge_attrs_configs = [edge_width_config, edge_color_config]
    required_edge_attrs = StyleService.collect_required_attributes(edge_attrs_configs)
    
    focus_node_attrs = set()
    if focus_config:
        focus_node_attrs = StyleService.collect_required_attributes([
            focus_config.get("node_size_config"),
            focus_config.get("node_color_config")
        ])

    # --- 2. Fetch Data ---
    global_node_attr_map, global_node_values = _fetch_node_data(db, network_id, global_node_attrs)
    edge_attr_map, edge_values = _fetch_edge_data(db, network_id, required_edge_attrs)
    
    focus_node_attr_map = {}
    focus_node_values = {}
    focus_node_map = {}
    
    # --- Validation: Ensure all requested attributes exist ---
    missing_attrs = []
    for attr in global_node_attrs:
        if attr not in global_node_attr_map:
            missing_attrs.append(f"Node attribute '{attr}'")
    
    for attr in required_edge_attrs:
        if attr not in edge_attr_map:
            missing_attrs.append(f"Edge attribute '{attr}'")
            
    if missing_attrs:
        raise ValueError(f"Missing required attributes for visualization: {', '.join(missing_attrs)}. Please calculate them first.")
        
    if focus_network_id:
        focus_node_map = _get_focus_node_map(db, focus_network_id)
        if focus_node_attrs:
             focus_node_attr_map, focus_node_values = _fetch_node_data(db, focus_network_id, focus_node_attrs)

    # --- 3. Calculate Stats ---
    node_size_stats = StyleService.calculate_stats(node_size_config, global_node_attr_map, global_node_values)
    node_color_stats = StyleService.calculate_stats(node_color_config, global_node_attr_map, global_node_values)
    edge_width_stats = StyleService.calculate_stats(edge_width_config, edge_attr_map, edge_values)
    edge_color_stats = StyleService.calculate_stats(edge_color_config, edge_attr_map, edge_values)
    
    focus_node_size_stats = (None, 0, 0)
    focus_node_color_stats = (None, 0, 0)
    if focus_config:
        focus_node_size_stats = StyleService.calculate_stats(focus_config.get("node_size_config"), focus_node_attr_map, focus_node_values)
        focus_node_color_stats = StyleService.calculate_stats(focus_config.get("node_color_config"), focus_node_attr_map, focus_node_values)

    # --- 4. Pre-calculate Maps ---
    ranking_color_map = StyleService.prepare_ranking_map(node_color_config, global_node_attr_map, global_node_values)
    categorical_color_map = StyleService.prepare_categorical_map(node_color_config, global_node_attr_map, global_node_values)
    
    custom_color_map = {}
    if custom_node_colors:
        for item in custom_node_colors:
            if "node_id" in item and "color" in item:
                custom_color_map[str(item["node_id"])] = item["color"]

    # --- 5. Build Nodes ---
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    smart_defaults = utils.calculate_smart_node_size(len(nodes))
    focus_node_ids_str = set(focus_node_map.keys())
    
    vis_nodes = []
    layout_x_attr = f"{layout_name}_x"
    layout_y_attr = f"{layout_name}_y"

    for n in nodes:
        is_focused = n.node_id in focus_node_ids_str
        
        if not is_focused and context_config and context_config.get("visible") is False:
            continue

        # Initial Global Styling
        size = StyleService.resolve_node_size(
            n.id, node_size_config, node_size_stats, 
            global_node_attr_map, global_node_values, smart_defaults
        )
        
        color = StyleService.resolve_node_color(
            n.id, str(n.node_id), node_color_config, node_color_stats,
            global_node_attr_map, global_node_values,
            ranking_color_map, categorical_color_map, custom_color_map
        )
        opacity = 1.0

        # Focus/Context Overrides
        if focus_network_id:
            if is_focused:
                if focus_config:
                    focus_db_id = focus_node_map.get(n.node_id)
                    if focus_db_id:
                        # Focus Size Override
                        f_size_conf = focus_config.get("node_size_config")
                        if f_size_conf:
                            size = StyleService.resolve_node_size(
                                focus_db_id, f_size_conf, focus_node_size_stats,
                                focus_node_attr_map, focus_node_values, smart_defaults
                            )
                        
                        # Focus Color Override
                        f_color_conf = focus_config.get("node_color_config")
                        if f_color_conf:
                            if f_color_conf.get("static_color"):
                                color = f_color_conf["static_color"]
                            else:
                                color = StyleService.resolve_node_color(
                                    focus_db_id, str(n.node_id), f_color_conf, focus_node_color_stats,
                                    focus_node_attr_map, focus_node_values,
                                    {}, {}, {}, default_color=color # Fallback to existing color
                                )
            else:
                # Context Styling
                if context_config:
                    opacity = context_config.get("opacity", 0.1)
                    if context_config.get("color"):
                        color = context_config["color"]
                    if context_config.get("size"):
                        size = context_config["size"]
                    elif not node_size_stats[0]:
                         size = smart_defaults["min"]

        # Layout
        x = StyleService.get_val(n.id, layout_x_attr, global_node_attr_map, global_node_values)
        y = StyleService.get_val(n.id, layout_y_attr, global_node_attr_map, global_node_values)
        if x is None: x = 0.5
        if y is None: y = 0.5

        # Label
        label = n.label
        if node_label_config and node_label_config.get("attribute"):
            val = StyleService.get_val(n.id, node_label_config["attribute"], global_node_attr_map, global_node_values)
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

    # --- 6. Build Edges ---
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    smart_edge_defaults = utils.calculate_smart_edge_width(len(edges))
    vis_edges = []
    
    node_lookup = {n.id: n for n in nodes}

    for e in edges:
        source_node = node_lookup.get(e.source_node_id)
        target_node = node_lookup.get(e.target_node_id)
        
        if not source_node or not target_node:
            continue
        
        is_focused = False
        if focus_network_id:
            is_focused = (source_node.node_id in focus_node_ids_str) and (target_node.node_id in focus_node_ids_str)

        if not is_focused and context_config and context_config.get("visible") is False:
            continue

        width = StyleService.resolve_edge_width(
            e.id, edge_width_config, edge_width_stats,
            edge_attr_map, edge_values, smart_edge_defaults
        )
        
        color = StyleService.resolve_edge_color(
             e.id, edge_color_config, edge_color_stats,
             edge_attr_map, edge_values
        )
        opacity = 1.0

        if focus_network_id and not is_focused:
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


# --- internal Helpers ---

def _fetch_node_data(db: Session, network_id: int, result_attrs: Set[str]) -> Tuple[Dict[str, int], Dict[int, Dict[int, Any]]]:
    if not result_attrs:
        return {}, {}
    
    defs = db.query(models.NodeAttribute).filter(
        models.NodeAttribute.network_id == network_id,
        models.NodeAttribute.attribute_name.in_(result_attrs)
    ).all()
    attr_map = {attr.attribute_name: attr.id for attr in defs}
    
    values = _fetch_attribute_values(db, models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, list(attr_map.values()))
    return attr_map, values

def _fetch_edge_data(db: Session, network_id: int, result_attrs: Set[str]) -> Tuple[Dict[str, int], Dict[int, Dict[int, Any]]]:
    if not result_attrs:
        return {}, {}
    
    defs = db.query(models.EdgeAttribute).filter(
        models.EdgeAttribute.network_id == network_id,
        models.EdgeAttribute.attribute_name.in_(result_attrs)
    ).all()
    attr_map = {attr.attribute_name: attr.id for attr in defs}
    
    values = _fetch_attribute_values(db, models.EdgeAttributeValue, models.EdgeFloatAttributeValue, models.EdgeTextAttributeValue, list(attr_map.values()))
    return attr_map, values

def _get_focus_node_map(db: Session, focus_network_id: int) -> Dict[str, int]:
    nodes = db.query(models.Node).filter(models.Node.network_id == focus_network_id).all()
    return {n.node_id: n.id for n in nodes}

def _fetch_attribute_values(db: Session, model_val, model_float, model_text, attr_ids: List[int]) -> Dict[int, Dict[int, Any]]:
    if not attr_ids: return {}
    
    q_float = db.query(model_val.node_id if model_val == models.NodeAttributeValue else model_val.edge_id, model_val.attribute_id, model_float.float_value)\
        .join(model_float, model_val.id == model_float.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_float.edge_attribute_value_id)\
        .filter(model_val.attribute_id.in_(attr_ids)).all()

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
