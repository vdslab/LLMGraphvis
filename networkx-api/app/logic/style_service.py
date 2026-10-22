import math
import unicodedata
from bisect import bisect_left, bisect_right
from typing import Any, Dict, List, NamedTuple, Set, Tuple

from app.logic import common_utils as utils

DEFAULT_NODE_GRADIENT = ["#C6DBEF", "#6BAED6", "#08306B"]
DEFAULT_EDGE_GRADIENT = ["#CCCCCC", "#000000"]
DEFAULT_EDGE_COLOR = "#999"


class NumericStats(NamedTuple):
    """The range one numeric mapping covers, and how values are placed in it.

    The first three fields keep the old ``(is_valid, min, max)`` shape. ``min``
    and ``max`` are the mapped range: the data range unless the config's
    ``value_min``/``value_max`` set it, in which case values beyond it are
    clamped to its ends (ADR 0029).
    """

    valid: bool
    min: float
    max: float
    transform: str = "linear"
    values: Tuple[float, ...] = ()  # sorted and clamped; read by "rank"
    log_offset: float = 1.0  # smallest positive gap above min; read by "log"

    def position(self, value: float) -> float:
        """Where `value` falls in the mapped range, from 0 (low end) to 1."""
        lo, hi = self.min, self.max
        if hi <= lo:
            return 0.0
        v = min(max(value, lo), hi)
        if self.transform == "log":
            # log of the distance from the low end, shifted so the low end (often
            # 0, e.g. betweenness of a leaf) stays finite and order is kept.
            base = math.log(self.log_offset)
            return (math.log(v - lo + self.log_offset) - base) / (
                math.log(hi - lo + self.log_offset) - base
            )
        if self.transform == "rank" and len(self.values) > 1:
            left = bisect_left(self.values, v)
            right = bisect_right(self.values, v)
            if right == left:  # not a data value: place it between neighbours
                return left / len(self.values)
            return ((left + right - 1) / 2) / (len(self.values) - 1)
        return (v - lo) / (hi - lo)


def _position(value: float, stats: Tuple) -> float:
    if isinstance(stats, NumericStats):
        return stats.position(value)
    lo, hi = stats[1], stats[2]
    if hi <= lo:
        return 0.0
    return min(max((value - lo) / (hi - lo), 0.0), 1.0)


class StyleService:
    """
    Service to handle all styling logic for determining node/edge size, color, and opacity.
    """

    @staticmethod
    def _category_key(value: str) -> str:
        """Return a conservative key for resolving trivial category variations."""
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return "".join(char for char in normalized if char.isalnum())

    @classmethod
    def reconcile_categorical_mapping(
        cls, provided_map: Dict[str, str], actual_values: Set[str]
    ) -> Dict[str, str]:
        """Match explicit color keys to categories that actually exist.

        Exact values win. A unique match after case/spacing/punctuation
        normalization is corrected to the stored value. Unknown or ambiguous
        keys are rejected so they cannot become phantom legend entries while
        the real category is silently auto-colored.
        """
        if not provided_map or not actual_values:
            return provided_map.copy()

        by_key: Dict[str, List[str]] = {}
        for value in actual_values:
            by_key.setdefault(cls._category_key(value), []).append(value)

        reconciled: Dict[str, str] = {}
        invalid: List[str] = []
        for requested, color in provided_map.items():
            if requested in actual_values:
                resolved = requested
            else:
                matches = by_key.get(cls._category_key(requested), [])
                if len(matches) != 1:
                    invalid.append(requested)
                    continue
                resolved = matches[0]

            if resolved in reconciled and reconciled[resolved] != color:
                raise ValueError(
                    f"Multiple colors were supplied for category '{resolved}'. "
                    "Use each exact category value only once."
                )
            reconciled[resolved] = color

        if invalid:
            supplied = ", ".join(repr(value) for value in sorted(invalid))
            available = ", ".join(repr(value) for value in sorted(actual_values))
            raise ValueError(
                f"Unknown or ambiguous categorical mapping value(s): {supplied}. "
                f"Available values are: {available}. Use values from the data exactly."
            )

        return reconciled

    @staticmethod
    def collect_required_attributes(configs: List[Dict[str, Any]]) -> Set[str]:
        """Collect all attribute names required by the given configurations."""
        attrs = set()
        for conf in configs:
            if conf and conf.get("attribute"):
                attrs.add(conf["attribute"])
        return attrs

    @staticmethod
    def calculate_stats(
        config: Dict[str, Any],
        attr_map: Dict[str, int],
        values_map: Dict[int, Dict[int, Any]],
    ) -> NumericStats:
        """The mapped range of a numeric attribute, with the config's transform.

        `valid` is False when the config names no attribute or the attribute
        has no numeric values (callers then fall back to defaults or treat it
        as categorical).
        """
        if not config or not config.get("attribute"):
            return NumericStats(False, 0, 0)

        attr_name = config["attribute"]
        if attr_name not in attr_map:
            return NumericStats(False, 0, 0)

        attr_id = attr_map[attr_name]
        vals = []
        for entity_vals in values_map.values():
            if attr_id in entity_vals:
                v = entity_vals[attr_id]
                if isinstance(v, (int, float)):
                    vals.append(v)

        if not vals:
            return NumericStats(False, 0, 0)

        lo = config.get("value_min")
        hi = config.get("value_max")
        lo = min(vals) if lo is None else lo
        hi = max(vals) if hi is None else hi
        if lo > hi:
            raise ValueError(
                f"value_min ({lo}) is above value_max ({hi}) for '{attr_name}', "
                f"whose values run from {min(vals)} to {max(vals)}."
            )

        transform = config.get("transform") or "linear"
        clamped = sorted(min(max(v, lo), hi) for v in vals)
        gaps = [v - lo for v in clamped if v > lo]
        return NumericStats(
            True,
            lo,
            hi,
            transform,
            tuple(clamped) if transform == "rank" else (),
            min(gaps) if gaps else 1.0,
        )

    @staticmethod
    def prepare_ranking_map(
        node_color_config: Dict[str, Any],
        global_node_attr_map: Dict[str, int],
        global_node_values: Dict[int, Dict[int, Any]],
    ) -> Dict[int, str]:
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
    def prepare_categorical_map(
        node_color_config: Dict[str, Any],
        global_node_attr_map: Dict[str, int],
        global_node_values: Dict[int, Dict[int, Any]],
    ) -> Dict[str, str]:
        """
        Pre-calculate a map of value_str -> color for CATEGORICAL scale type.
        Assigns a named palette up to its capacity, then falls back to Gray.
        """
        categorical_color_map = {}
        if node_color_config and node_color_config.get("scale_type") == "CATEGORICAL":
            attr_name = node_color_config.get("attribute")
            provided_map = node_color_config.get("color_map")

            # Defensive check: ensure provided_map is a dict
            if provided_map is None or not isinstance(provided_map, dict):
                provided_map = {}

            if attr_name in global_node_attr_map:
                attr_id = global_node_attr_map[attr_name]

                # Count frequencies
                value_counts = {}
                for attrs in global_node_values.values():
                    if attr_id in attrs:
                        val_str = str(attrs[attr_id])
                        value_counts[val_str] = value_counts.get(val_str, 0) + 1

                provided_map = StyleService.reconcile_categorical_mapping(
                    provided_map, set(value_counts)
                )

            categorical_color_map = provided_map.copy()

            if attr_name in global_node_attr_map:
                # Sort by frequency desc
                sorted_values = sorted(
                    value_counts.keys(), key=lambda k: value_counts[k], reverse=True
                )

                # Identify values needing colors (not in provided_map)
                needed_values = [
                    v for v in sorted_values if v not in categorical_color_map
                ]

                palette_name = node_color_config.get("palette")
                if not palette_name:
                    palette_name = utils.choose_categorical_palette(len(sorted_values))
                node_color_config["palette"] = palette_name

                # Anything beyond the selected palette's capacity falls back
                # to default_color. Cycling would make categories ambiguous.

                if needed_values:
                    palette = utils.generate_categorical_palette(
                        len(sorted_values), palette_name
                    )
                    limit = len(palette)

                    is_fixed = node_color_config.get("fixed_mapping", False)
                    if not is_fixed:
                        assigned_count = len(categorical_color_map)
                        for val in needed_values:
                            if assigned_count < limit:
                                categorical_color_map[val] = palette[assigned_count]
                                assigned_count += 1
                            else:
                                break

            # Update the config in place so it persists
            node_color_config["color_map"] = categorical_color_map

            # Ensure default color is Gray if not specified, to handle "Others"
            if "default_color" not in node_color_config:
                node_color_config["default_color"] = utils.GRAY_COLOR

        return categorical_color_map

    @staticmethod
    def get_val(
        entity_id: int,
        attr_name: str,
        attr_map: Dict[str, int],
        values_map: Dict[int, Dict[int, Any]],
    ) -> Any:
        """Helper to safely get a value for an entity."""
        if attr_name not in attr_map:
            return None
        attr_id = attr_map[attr_name]
        if entity_id in values_map and attr_id in values_map[entity_id]:
            return values_map[entity_id][attr_id]
        return None

    @classmethod
    def resolve_node_size(
        cls,
        db_id: int,
        config: Dict[str, Any],
        stats: Tuple[bool, float, float],
        attr_map: Dict[str, int],
        values_map: Dict[int, Dict[int, Any]],
        smart_defaults: Dict[str, float],
    ) -> float:
        """Resolve node size based on config and stats."""
        size = smart_defaults["default"]
        if config and config.get("default") is not None:
            size = config["default"]
        if config and stats[0]:
            val = cls.get_val(db_id, config["attribute"], attr_map, values_map)
            if isinstance(val, (int, float)):
                target_min = config.get("min")
                if target_min is None:
                    target_min = smart_defaults["min"]
                
                target_max = config.get("max")
                if target_max is None:
                    target_max = smart_defaults["max"]
                    
                size = utils.normalize(
                    _position(val, stats), 0.0, 1.0, target_min, target_max
                )
        
        # Apply scaling factor if present
        if config:
            scaling_factor = config.get("scaling_factor", 1.0)
            if scaling_factor != 1.0:
                size *= scaling_factor
                
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
        default_color: str = "#5384ED",
    ) -> str:
        """Resolve node color based on various strategies (custom, linear, categorical, ranking)."""
        # 1. Custom specific color
        if node_id_str in custom_color_map:
            return custom_color_map[node_id_str]

        # 2. Config-based coloring
        should_color = False
        if config:
            if stats[0]:  # Linear stats valid
                should_color = True
            elif (
                config.get("scale_type") == "CATEGORICAL"
                and config.get("attribute") in attr_map
            ):
                should_color = True
            elif (
                config.get("scale_type") == "RANKING"
            ):  # Ranking check could be stricter
                should_color = True

        if should_color:
            scale_type = config.get("scale_type", "LINEAR")

            if scale_type == "LINEAR":
                val = cls.get_val(db_id, config.get("attribute"), attr_map, values_map)
                if isinstance(val, (int, float)) and stats[0]:
                    gradient = (config.get("gradient") or DEFAULT_NODE_GRADIENT)
                    return utils.interpolate_gradient(
                        _position(val, stats), 0.0, 1.0, gradient
                    )

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
    def resolve_edge_width(
        cls,
        db_id: int,
        config: Dict[str, Any],
        stats: Tuple[bool, float, float],
        attr_map: Dict[str, int],
        values_map: Dict[int, Dict[int, Any]],
        smart_defaults: Dict[str, float],
    ) -> float:
        width = smart_defaults["default"]
        if config and config.get("default") is not None:
            width = config["default"]
        if config and stats[0]:
            val = cls.get_val(db_id, config["attribute"], attr_map, values_map)
            if isinstance(val, (int, float)):
                target_min = config.get("min")
                if target_min is None:
                    target_min = smart_defaults["min"]
                
                target_max = config.get("max")
                if target_max is None:
                    target_max = smart_defaults["max"]
                    
                width = utils.normalize(
                    _position(val, stats), 0.0, 1.0, target_min, target_max
                )
        return width

    @classmethod
    def resolve_edge_color(
        cls,
        db_id: int,
        config: Dict[str, Any],
        stats: Tuple[bool, float, float],
        attr_map: Dict[str, int],
        values_map: Dict[int, Dict[int, Any]],
    ) -> str:
        default = (config or {}).get("default_color") or DEFAULT_EDGE_COLOR
        if not config or not config.get("attribute"):
            return default
        val = cls.get_val(db_id, config["attribute"], attr_map, values_map)
        scale_type = config.get("scale_type", "LINEAR")
        if scale_type == "LINEAR" and stats[0] and isinstance(val, (int, float)):
            gradient = config.get("gradient") or DEFAULT_EDGE_GRADIENT
            return utils.interpolate_gradient(
                _position(val, stats), 0.0, 1.0, gradient
            )
        if scale_type == "CATEGORICAL" and val is not None:
            color_map = config.get("color_map") or {}
            if str(val) in color_map:
                return color_map[str(val)]
        return default
