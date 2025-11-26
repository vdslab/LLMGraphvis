def normalize(value, min_val, max_val, target_min, target_max):
    """
    Normalize a value to a target range.
    """
    if max_val == min_val: return target_min
    return target_min + ((value - min_val) / (max_val - min_val)) * (target_max - target_min)

def interpolate_color(value: float, min_val: float, max_val: float, start_color: str, end_color: str) -> str:
    """
    Interpolate between two hex colors.
    """
    if max_val == min_val:
        return start_color
        
    ratio = (value - min_val) / (max_val - min_val)
    ratio = max(0, min(1, ratio)) # Clamp
    
    # Parse hex
    def hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        
    s_rgb = hex_to_rgb(start_color)
    e_rgb = hex_to_rgb(end_color)
    
    # Interpolate
    r = int(s_rgb[0] + (e_rgb[0] - s_rgb[0]) * ratio)
    g = int(s_rgb[1] + (e_rgb[1] - s_rgb[1]) * ratio)
    b = int(s_rgb[2] + (e_rgb[2] - s_rgb[2]) * ratio)
    
    return f"#{r:02x}{g:02x}{b:02x}"

def calculate_smart_node_size(num_nodes: int) -> dict:
    """
    Calculate smart default node sizes based on graph size.
    Returns a dict with 'default', 'min', 'max'.
    """
    if num_nodes <= 0:
        return {"default": 20, "min": 5, "max": 50}
        
    # Heuristic: Larger graphs need smaller nodes
    # Formula: base = 300 / sqrt(N), clamped between 3 and 30
    import math
    base_size = 300 / math.sqrt(num_nodes)
    base_size = max(3, min(30, base_size))
    
    return {
        "default": round(base_size, 1),
        "min": round(base_size * 0.5, 1),
        "max": round(base_size * 2.5, 1)
    }

def calculate_smart_edge_width(num_edges: int) -> dict:
    """
    Calculate smart default edge widths based on graph size (number of edges).
    Returns a dict with 'default', 'min', 'max'.
    """
    if num_edges <= 0:
        return {"default": 1.0, "min": 0.5, "max": 5.0}
        
    # Heuristic: Dense graphs need thinner edges
    # Formula: base = 50 / sqrt(E), clamped between 0.2 and 5
    import math
    base_width = 50 / math.sqrt(num_edges)
    base_width = max(0.2, min(5.0, base_width))
    
    return {
        "default": round(base_width, 1),
        "min": round(base_width * 0.5, 1),
        "max": round(base_width * 3.0, 1)
    }
