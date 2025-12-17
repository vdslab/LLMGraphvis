from typing import Dict, Any, List, Set, Tuple, Optional
from app.logic import common_utils as utils

class StyleService:
    """
    Service to handle all styling logic for determining node/edge size, color, and opacity.
    """

    @staticmethod
    def collect_required_attributes(configs: List[Dict[str, Any]]) -> Set[str]:
        """Collect all attribute names required by the given configurations."""
        attrs = set()
        for conf in configs:
            if conf and conf.get("attribute"):
                attrs.add(conf["attribute"])
        return attrs

    @staticmethod
    def calculate_stats(config: Dict[str, Any], attr_map: Dict[str, int], values_map: Dict[int, Dict[int, Any]]) -> Tuple[bool, float, float]:
        """
        Calculate min/max statistics for a numeric attribute.
        Returns (is_valid, min_val, max_val).
        """
        if not config or not config.get("attribute"):
            return False, 0, 0
            
        attr_name = config["attribute"]
        if attr_name not in attr_map:
            return False, 0, 0
        
        attr_id = attr_map[attr_name]
        vals = []
        for entity_vals in values_map.values():
            if attr_id in entity_vals:
                v = entity_vals[attr_id]
                if isinstance(v, (int, float)):
                    vals.append(v)
        
        if not vals:
            return False, 0, 0
            
        return True, min(vals), max(vals)

    @staticmethod
    def prepare_ranking_map(node_color_config: Dict[str, Any], global_node_attr_map: Dict[str, int], global_node_values: Dict[int, Dict[int, Any]]) -> Dict[int, str]:
        """
        Pre-calculate a map of node_id -> color for RANKING scale type.
        """
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
                
                # Sort descending
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
                    if current_idx >= len(values_list):
                        break
        return ranking_color_map

    @staticmethod
    def prepare_categorical_map(node_color_config: Dict[str, Any], global_node_attr_map: Dict[str, int], global_node_values: Dict[int, Dict[int, Any]]) -> Dict[str, str]:
        """
        Pre-calculate a map of value_str -> color for CATEGORICAL scale type.
        Implements Top-N (default 10) logic, assigning 'Others' to Gray.
        """
        categorical_color_map = {}
        if node_color_config and node_color_config.get("scale_type") == "CATEGORICAL":
            attr_name = node_color_config.get("attribute")
            provided_map = node_color_config.get("color_map")
            
            # Defensive check: ensure provided_map is a dict
            if provided_map is None or not isinstance(provided_map, dict):
                provided_map = {}
                
            categorical_color_map = provided_map.copy()

            if attr_name in global_node_attr_map:
                attr_id = global_node_attr_map[attr_name]
                
                # Count frequencies
                value_counts = {}
                for attrs in global_node_values.values():
                    if attr_id in attrs:
                        val_str = str(attrs[attr_id])
                        value_counts[val_str] = value_counts.get(val_str, 0) + 1
                
                # Sort by frequency desc
                sorted_values = sorted(value_counts.keys(), key=lambda k: value_counts[k], reverse=True)
                
                # Identify values needing colors (not in provided_map)
                needed_values = [v for v in sorted_values if v not in categorical_color_map]
                
                # Only auto-fill if no explicitly set default color (or we want to override/augment)
                # Strategy: We fill up to 10 distinct colors. 
                # Anything else falls back to default_color, which we set to Gray if not set.
                
                # If default_color IS provided, we assume the user wants strict mapping + default for everything else.
                should_autofill = "default_color" not in node_color_config
                
                if should_autofill and needed_values:
                    # We only support 20 distinct colors + Gray
                    limit = 20
                    # Check how many colors already used in provided_map to avoid collisions? 
                    # Simplicity: Just assign from palette to the top N needed values.
                    
                    palette = utils.generate_categorical_palette(limit)
                    
                    # Values that are "Top N" get a color. 
                    # Others get nothing in the map -> Fallback to default.
                    
                    assigned_count = len(categorical_color_map)
                    for val in needed_values:
                        if assigned_count < limit:
                             # Find next unused color in palette?
                             # For now, simplistic assignment:
                             if assigned_count < len(palette):
                                 categorical_color_map[val] = palette[assigned_count]
                                 assigned_count += 1
                        else:
                            # Reached limit, stop assigning distinct colors.
                            # These will use default_color.
                            break
            
            # Update the config in place so it persists
            node_color_config["color_map"] = categorical_color_map
            
            # Ensure default color is Gray if not specified, to handle "Others"
            if "default_color" not in node_color_config:
                node_color_config["default_color"] = utils.GRAY_COLOR

        return categorical_color_map


    @staticmethod
    def get_val(entity_id: int, attr_name: str, attr_map: Dict[str, int], values_map: Dict[int, Dict[int, Any]]) -> Any:
        """Helper to safely get a value for an entity."""
        if attr_name not in attr_map:
            return None
        attr_id = attr_map[attr_name]
        if entity_id in values_map and attr_id in values_map[entity_id]:
            return values_map[entity_id][attr_id]
        return None

    @classmethod
    def resolve_node_size(cls, db_id: int, config: Dict[str, Any], stats: Tuple[bool, float, float], 
                          attr_map: Dict[str, int], values_map: Dict[int, Dict[int, Any]], 
                          smart_defaults: Dict[str, float]) -> float:
        """Resolve node size based on config and stats."""
        size = smart_defaults["default"]
        if config and stats[0]:
            val = cls.get_val(db_id, config["attribute"], attr_map, values_map)
            if isinstance(val, (int, float)):
                target_min = config.get("min", smart_defaults["min"])
                target_max = config.get("max", smart_defaults["max"])
                size = utils.normalize(val, stats[1], stats[2], target_min, target_max)
        return size

    @classmethod
    def resolve_node_color(
        cls, 
        db_id: int, 
        node_id_str: str,
        config: Dict[str, Any], 
        stats: Tuple[bool, float, float],
        attr_map: Dict[str, int], 
        values_map: Dict[int, Dict[int, Any]],
        ranking_map: Dict[int, str],
        categorical_map: Dict[str, str],
        custom_color_map: Dict[str, str],
        default_color: str = "#5384ED"
    ) -> str:
        """Resolve node color based on various strategies (custom, linear, categorical, ranking)."""
        # 1. Custom specific color
        if node_id_str in custom_color_map:
            return custom_color_map[node_id_str]

        # 2. Config-based coloring
        should_color = False
        if config:
            if stats[0]: # Linear stats valid
                should_color = True
            elif config.get("scale_type") == "CATEGORICAL" and config.get("attribute") in attr_map:
                should_color = True
            elif config.get("scale_type") == "RANKING": # Ranking check could be stricter
                should_color = True

        if should_color:
            scale_type = config.get("scale_type", "LINEAR")
            
            if scale_type == "LINEAR":
                val = cls.get_val(db_id, config.get("attribute"), attr_map, values_map)
                if isinstance(val, (int, float)) and stats[0]:
                    gradient = config.get("gradient", ["#d1e0ff", "#003399"])
                    return utils.interpolate_color(val, stats[1], stats[2], gradient[0], gradient[1])
            
            elif scale_type == "CATEGORICAL":
                val = cls.get_val(db_id, config.get("attribute"), attr_map, values_map)
                if str(val) in categorical_map:
                    return categorical_map[str(val)]
            
            elif scale_type == "RANKING":
                if db_id in ranking_map:
                    return ranking_map[db_id]

        # 3. Default
        return config.get("default_color", default_color) if config else default_color

    @classmethod
    def resolve_edge_width(cls, db_id: int, config: Dict[str, Any], stats: Tuple[bool, float, float],
                           attr_map: Dict[str, int], values_map: Dict[int, Dict[int, Any]],
                           smart_defaults: Dict[str, float]) -> float:
        width = smart_defaults["default"]
        if config and stats[0]:
            val = cls.get_val(db_id, config["attribute"], attr_map, values_map)
            if isinstance(val, (int, float)):
                target_min = config.get("min", smart_defaults["min"])
                target_max = config.get("max", smart_defaults["max"])
                width = utils.normalize(val, stats[1], stats[2], target_min, target_max)
        return width

    @classmethod
    def resolve_edge_color(cls, db_id: int, config: Dict[str, Any], stats: Tuple[bool, float, float],
                           attr_map: Dict[str, int], values_map: Dict[int, Dict[int, Any]]) -> str:
        color = "#999" # Default
        if config and stats[0]:
            val = cls.get_val(db_id, config["attribute"], attr_map, values_map)
            scale_type = config.get("scale_type", "LINEAR")
            if scale_type == "LINEAR" and isinstance(val, (int, float)):
                gradient = config.get("gradient", ["#eeeeee", "#000000"])
                color = utils.interpolate_color(val, stats[1], stats[2], gradient[0], gradient[1])
            elif scale_type == "CATEGORICAL":
                color_map = config.get("color_map")
                if not color_map:
                    color_map = {}
                if str(val) in color_map:
                    color = color_map[str(val)]
        return color
