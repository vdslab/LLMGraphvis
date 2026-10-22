import colorsys

def normalize(value, min_val, max_val, target_min, target_max):
    """
    Normalize a value to a target range.
    """
    if max_val == min_val:
        return target_min
    return target_min + ((value - min_val) / (max_val - min_val)) * (
        target_max - target_min
    )


def interpolate_color(
    value: float, min_val: float, max_val: float, start_color: str, end_color: str
) -> str:
    """
    Interpolate between two colors (hex or names).
    """
    if max_val == min_val:
        return start_color

    ratio = (value - min_val) / (max_val - min_val)
    ratio = max(0, min(1, ratio))  # Clamp

    # Basic color map for common names
    COLOR_MAP = {
        "red": "#FF0000",
        "green": "#008000",
        "blue": "#0000FF",
        "white": "#FFFFFF",
        "black": "#000000",
        "yellow": "#FFFF00",
        "cyan": "#00FFFF",
        "magenta": "#FF00FF",
        "gray": "#808080",
        "grey": "#808080",
        "orange": "#FFA500",
        "purple": "#800080",
        "pink": "#FFC0CB",
        "brown": "#A52A2A",
        "lightgray": "#D3D3D3",
        "darkgray": "#A9A9A9",
    }

    def resolve_color(c):
        if c.lower() in COLOR_MAP:
            return COLOR_MAP[c.lower()]
        return c

    # Parse hex
    def hex_to_rgb(h):
        try:
            h = h.lstrip("#")
            if len(h) == 3:  # Handle short hex #RGB
                h = "".join([c * 2 for c in h])
            return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
        except Exception:
            # Fallback to black if parsing fails
            return (0, 0, 0)

    s_rgb = hex_to_rgb(resolve_color(start_color))
    e_rgb = hex_to_rgb(resolve_color(end_color))

    # Convert to HSL (0..1 range)
    s_hls = colorsys.rgb_to_hls(s_rgb[0] / 255.0, s_rgb[1] / 255.0, s_rgb[2] / 255.0)
    e_hls = colorsys.rgb_to_hls(e_rgb[0] / 255.0, e_rgb[1] / 255.0, e_rgb[2] / 255.0)

    # Interpolate in HSL space with Shortest Path Hue logic
    h1, l1, s1 = s_hls
    h2, l2, s2 = e_hls

    # Calculate hue difference
    mh = h2 - h1
    
    # Shortest path logic for Hue (circular 0..1)
    if mh > 0.5:
        mh -= 1.0
    elif mh < -0.5:
        mh += 1.0
        
    h = h1 + mh * ratio
    # Normalize back to 0..1
    h = h % 1.0
    
    l = l1 + (l2 - l1) * ratio
    s = s1 + (s2 - s1) * ratio
    
    # Back to RGB
    r_float, g_float, b_float = colorsys.hls_to_rgb(h, l, s)
    
    r = round(r_float * 255)
    g = round(g_float * 255)
    b = round(b_float * 255)

    return f"#{r:02x}{g:02x}{b:02x}"


def interpolate_gradient(
    value: float, min_val: float, max_val: float, colors: list[str]
) -> str:
    """
    Interpolate color from a list of colors (gradient stops).
    Distributes stops evenly across the range [min_val, max_val].
    """
    if not colors:
        return "#000000"
    if len(colors) == 1:
        return colors[0]
    
    if max_val == min_val:
        return colors[0]

    # Normalize value to 0..1
    t = (value - min_val) / (max_val - min_val)
    t = max(0.0, min(1.0, t))

    # Determine which segment of the gradient we are in
    # If n colors, we have n-1 segments.
    # segment index i corresponds to t in [i/(n-1), (i+1)/(n-1)]
    
    n_colors = len(colors)
    segment_length = 1.0 / (n_colors - 1)
    
    segment_idx = int(t / segment_length)
    # Handle the exact 1.0 case
    if segment_idx >= n_colors - 1:
        segment_idx = n_colors - 2
        
    # Local ratio within the segment
    # local_t goes from 0 to 1 as we move from colors[i] to colors[i+1]
    segment_start_t = segment_idx * segment_length
    local_t = (t - segment_start_t) / segment_length
    
    c1 = colors[segment_idx]
    c2 = colors[segment_idx + 1]
    
    # Use existing single-step interpolation, mapping local_t back to range logic
    # We can cheat and just recurse interpolate_color with min=0, max=1, val=local_t
    return interpolate_color(local_t, 0.0, 1.0, c1, c2)


def calculate_smart_node_size(num_nodes: int) -> dict:
    """
    Calculate smart default node sizes based on graph size.
    Returns a dict with 'default', 'min', 'max'.
    """
    if num_nodes <= 0:
        return {"default": 20, "min": 5, "max": 50}

    # Heuristic: Larger graphs need smaller nodes
    # Formula: base = 600 / sqrt(N)
    # Target: 
    #   N=30  -> ~110 size -> Radius ~ 19 (in 2000px space) -> Good visibility
    #   N=1000 -> ~19 size  -> Radius ~ 8 (in 2000px space) -> Small, readable dots
    import math

    base_size = 600 / math.sqrt(num_nodes)
    base_size = max(5.0, min(200.0, base_size))

    return {
        "default": round(base_size * 2.0, 1),
        "min": round(base_size * 1.0, 1),
        "max": round(base_size * 5.0, 1),
    }


def calculate_smart_edge_width(num_edges: int) -> dict:
    """
    Calculate smart default edge widths based on graph size (number of edges).
    Returns a dict with 'default', 'min', 'max'.
    """
    if num_edges <= 0:
        return {"default": 2.0, "min": 0.5, "max": 10.0}

    # Heuristic: Dense graphs need thinner edges
    # Formula: base = 150 / sqrt(E)
    # Target:
    #   E=50   -> ~21?? No wait, 150/7 = 21. Maybe too thick? 
    #   Let's check the plan: Target ~5-8 units for low density.
    #   150 / sqrt(50) = 21... The plan said 150 but maybe meant a bit less or I should clamp stricter?
    #   Plan said "Target ~5-8 units". 
    #   If E=50, sqrt(50)=7. 150/7 = 21. That is very thick.
    #   Maybe 50 / sqrt(E) was better? 50/7 = 7. 
    #   Wait, the plan approved was 150. But 21px edge on 2000px canvas is 1%. That's okay.
    #   Let's stick to the plan but maybe lower the clamp if it gets too crazy.
    import math

    base_width = 150 / math.sqrt(num_edges)
    base_width = max(0.2, min(10.0, base_width))

    return {
        "default": round(base_width, 1),
        "min": round(base_width * 0.5, 1),
        "max": round(base_width * 3.0, 1),
    }


# D3 scale-chromatic categorical schemes, preserving the official order.
# Source: https://d3js.org/d3-scale-chromatic/categorical
D3_CATEGORICAL_PALETTES = {
    "accent": [
        "#7fc97f", "#beaed4", "#fdc086", "#ffff99", "#386cb0", "#f0027f",
        "#bf5b17", "#666666",
    ],
    "category10": [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
        "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ],
    "dark2": [
        "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02",
        "#a6761d", "#666666",
    ],
    "observable10": [
        "#4269d0", "#efb118", "#ff725c", "#6cc5b0", "#3ca951", "#ff8ab7",
        "#a463f2", "#97bbf5", "#9c6b4e", "#9498a0",
    ],
    "paired": [
        "#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99", "#e31a1c",
        "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a", "#ffff99", "#b15928",
    ],
    "pastel1": [
        "#fbb4ae", "#b3cde3", "#ccebc5", "#decbe4", "#fed9a6", "#ffffcc",
        "#e5d8bd", "#fddaec", "#f2f2f2",
    ],
    "pastel2": [
        "#b3e2cd", "#fdcdac", "#cbd5e8", "#f4cae4", "#e6f5c9", "#fff2ae",
        "#f1e2cc", "#cccccc",
    ],
    "set1": [
        "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33",
        "#a65628", "#f781bf", "#999999",
    ],
    "set2": [
        "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f",
        "#e5c494", "#b3b3b3",
    ],
    "set3": [
        "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
        "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd", "#ccebc5", "#ffed6f",
    ],
    "tableau10": [
        "#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f", "#edc949",
        "#af7aa1", "#ff9da7", "#9c755f", "#bab0ab",
    ],
}

# Compatibility palette for data with more categories than D3's 12-color maximum.
EXTENDED_20_PALETTE = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
    "#e377c2",  # Pink
    "#7f7f7f",  # Gray (Keep for now or replace?) -> Replace with Teal
    "#bcbd22",  # Olive
    "#17becf",  # Cyan
    "#aec7e8",  # Light Blue
    "#ffbb78",  # Light Orange
    "#98df8a",  # Light Green
    "#ff9896",  # Light Red
    "#c5b0d5",  # Light Purple
    "#c49c94",  # Light Brown
    "#f7b6d2",  # Light Pink
    "#dbdb8d",  # Light Olive
    "#9edae5",  # Light Cyan
    "#393b79",  # Indigo
]

D3_CATEGORICAL_PALETTES["extended20"] = EXTENDED_20_PALETTE


GRAY_COLOR = "#d3d3d3"  # Light Gray for "Others"


def choose_categorical_palette(category_count: int) -> str:
    """Choose the default named palette for the number of real categories."""
    if category_count <= 10:
        return "tableau10"
    if category_count <= 12:
        return "paired"
    return "extended20"


def generate_categorical_palette(n: int, palette_name: str | None = None) -> list:
    """Return up to ``n`` colors without cycling a categorical palette."""
    selected = palette_name or choose_categorical_palette(n)
    base_palette = D3_CATEGORICAL_PALETTES[selected]
    return base_palette[:n]
