
import networkx as nx
import numpy as np

def calculate_spread(pos):
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    
    area = width * height
    
    # Also calculate average distance from center
    center_x = sum(xs) / len(xs)
    center_y = sum(ys) / len(ys)
    avg_dist = np.mean([np.sqrt((x - center_x)**2 + (y - center_y)**2) for x, y in pos.values()])
    
    return area, avg_dist

def main():
    print("Generating test graph...")
    G = nx.watts_strogatz_graph(100, 6, 0.1, seed=42)
    
    print("Calculating layout with OLD parameters (scaling_ratio=2.0)...")
    pos_old = nx.forceatlas2_layout(G, max_iter=2000, scaling_ratio=2.0, seed=42)
    area_old, avg_dist_old = calculate_spread(pos_old)
    print(f"Old Area: {area_old:.2f}, Average Distance from Center: {avg_dist_old:.2f}")

    print("Calculating layout with NEW parameters (scaling_ratio=100.0)...")
    pos_new = nx.forceatlas2_layout(G, max_iter=3000, scaling_ratio=100.0, seed=42)
    area_new, avg_dist_new = calculate_spread(pos_new)
    print(f"New Area: {area_new:.2f}, Average Distance from Center: {avg_dist_new:.2f}")
    
    # Assert improvement
    assert area_new > area_old, "New layout should occupy more area"
    assert avg_dist_new > avg_dist_old, "Nodes should be further from center on average"
    
    ratio = area_new / area_old
    print(f"Area Improvements Ratio: {ratio:.2f}x")
    
    if ratio > 5.0:
        print("✅ SUCCESS: Significant spread improvement verified.")
    else:
        print("⚠️ WARNING: Improvement might be marginal.")

if __name__ == "__main__":
    main()
