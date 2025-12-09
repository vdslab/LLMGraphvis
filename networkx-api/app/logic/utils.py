def normalize(value, min_val, max_val, target_min, target_max):
    """
    Normalize a value to a target range.
    """
    if max_val == min_val: return target_min
    return target_min + ((value - min_val) / (max_val - min_val)) * (target_max - target_min)

def interpolate_color(value: float, min_val: float, max_val: float, start_color: str, end_color: str) -> str:
    """
    Interpolate between two colors (hex or names).
    """
    if max_val == min_val:
        return start_color
        
    ratio = (value - min_val) / (max_val - min_val)
    ratio = max(0, min(1, ratio)) # Clamp
    
    # Basic color map for common names
    COLOR_MAP = {
        "red": "#FF0000", "green": "#008000", "blue": "#0000FF",
        "white": "#FFFFFF", "black": "#000000", "yellow": "#FFFF00",
        "cyan": "#00FFFF", "magenta": "#FF00FF", "gray": "#808080",
        "grey": "#808080", "orange": "#FFA500", "purple": "#800080",
        "pink": "#FFC0CB", "brown": "#A52A2A", "lightgray": "#D3D3D3",
        "darkgray": "#A9A9A9"
    }
    
    def resolve_color(c):
        if c.lower() in COLOR_MAP: return COLOR_MAP[c.lower()]
        return c

    # Parse hex
    def hex_to_rgb(h):
        try:
            h = h.lstrip('#')
            if len(h) == 3: # Handle short hex #RGB
                h = ''.join([c*2 for c in h])
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            # Fallback to black if parsing fails
            return (0, 0, 0)
        
    s_rgb = hex_to_rgb(resolve_color(start_color))
    e_rgb = hex_to_rgb(resolve_color(end_color))
    
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

def generate_categorical_palette(n: int) -> list:
    """
    Generate a list of n distinct hex colors.
    """
    # A standard qualitative palette (Tableau 20 / d3.schemeCategory20 like)
    base_palette = [
        "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c", "#98df8a",
        "#d62728", "#ff9896", "#9467bd", "#c5b0d5", "#8c564b", "#c49c94",
        "#e377c2", "#f7b6d2", "#7f7f7f", "#c7c7c7", "#bcbd22", "#dbdb8d",
        "#17becf", "#9edae5"
    ]
    
    if n <= len(base_palette):
        return base_palette[:n]
    
    # If we need more, we might need to generate them or cycle
    # For now, let's just cycle if > 20, but maybe with a slight modification?
    # Simple cycling:
    palette = []
    for i in range(n):
        palette.append(base_palette[i % len(base_palette)])
    return palette
