from sqlalchemy.orm import Session
from app import models
from app.logic.visualization_builder import VisualizationBuilder
from typing import Dict, Any, List, Set, Tuple, Optional

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
    # --- Validation ---
    _validate_node_color_config(node_color_config)
    _validate_node_size_config(node_size_config)
    _validate_edge_configs(edge_width_config, edge_color_config)
    
    # --- Build Visualization ---
    builder = VisualizationBuilder(
        network_id=network_id,
        db=db,
        layout_name=layout_name,
        node_size_config=node_size_config,
        node_color_config=node_color_config,
        edge_width_config=edge_width_config,
        edge_color_config=edge_color_config,
        focus_network_id=focus_network_id,
        context_config=context_config,
        focus_config=focus_config,
        custom_node_colors=custom_node_colors,
        node_label_config=node_label_config
    )
    
    builder.validate_and_prepare()
    builder.fetch_data()
    builder.calculate_statistics()
    return builder.build()

# --- internal Validators ---

def _validate_config_keys(config: Dict, allowed_keys: Set[str], config_name: str):
    """Raises ValueError if config contains unknown keys."""
    if not config: return
    unknown = set(config.keys()) - allowed_keys
    if unknown:
        raise ValueError(f"Invalid keys in {config_name}: {unknown}. Allowed: {allowed_keys}")

def _validate_node_color_config(config: Optional[Dict]):
    if not config: return
    allowed = {"attribute", "scale_type", "gradient", "color_map", "ranking_rules", "default_color"}
    _validate_config_keys(config, allowed, "node_color_config")
    
    if "attribute" not in config and "scale_type" in config and config["scale_type"] != "STATIC":
         # Maybe static doesn't need attribute, but others do
         pass 

    if "scale_type" in config:
        if config["scale_type"] not in ["LINEAR", "CATEGORICAL", "RANKING"]:
            raise ValueError(f"Invalid scale_type: {config['scale_type']}. Must be LINEAR, CATEGORICAL, or RANKING.")

def _validate_node_size_config(config: Optional[Dict]):
    if not config: return
    allowed = {"attribute", "min", "max", "default"}
    _validate_config_keys(config, allowed, "node_size_config")

def _validate_edge_configs(width_config: Optional[Dict], color_config: Optional[Dict]):
    if width_config:
        allowed = {"attribute", "min", "max", "default"}
        _validate_config_keys(width_config, allowed, "edge_width_config")
    
    if color_config:
        allowed = {"attribute", "scale_type", "gradient", "color_map", "default_color"}
        _validate_config_keys(color_config, allowed, "edge_color_config")
        if "scale_type" in color_config and color_config["scale_type"] not in ["LINEAR", "CATEGORICAL"]:
             raise ValueError(f"Invalid edge scale_type: {color_config['scale_type']}")
