
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import networkx as nx
from app.logic.layout import determine_layout_params

def verify_params(num_nodes, num_edges, expected_iter_min, expected_iter_max, expected_scaling_min, expected_scaling_max):
    G = nx.Graph()
    G.add_nodes_from(range(num_nodes))
    if num_nodes > 1 and num_edges > 0:
        # Create random edges
        import random
        random.seed(42)
        possible_edges = [(u, v) for u in range(num_nodes) for v in range(u + 1, num_nodes)]
        # Sample if possible (for small N) or just add sequentially for speed in mock
        if len(possible_edges) >= num_edges:
             chosen_edges = random.sample(possible_edges, num_edges)
             G.add_edges_from(chosen_edges)
        else:
             # Just add full graph
             G.add_edges_from(possible_edges)

    params = determine_layout_params(G, "forceatlas2")
    
    max_iter = params["max_iter"]
    scaling_ratio = params["scaling_ratio"]
    avg_degree = (2 * len(G.edges)) / num_nodes if num_nodes > 0 else 0
    
    print(f"Nodes: {num_nodes}, Edges: {len(G.edges)}, AvgDeg: {avg_degree:.2f} -> max_iter: {max_iter}, scaling: {scaling_ratio:.2f}")
    
    if not (expected_iter_min <= max_iter <= expected_iter_max):
        print(f"FAIL: max_iter {max_iter} not in range [{expected_iter_min}, {expected_iter_max}]")
        return False

    if not (expected_scaling_min <= scaling_ratio <= expected_scaling_max):
        print(f"FAIL: scaling_ratio {scaling_ratio} not in range [{expected_scaling_min}, {expected_scaling_max}]")
        return False
        
    if params["jitter_tolerance"] != 1.0:
         print(f"FAIL: jitter_tolerance is {params['jitter_tolerance']}, expected 1.0")
         return False

    return True

def main():
    print("Verifying ForceAtlas2 Dynamic Scaling (Iterations & Overlap)...")
    
    # Test cases: (num_nodes, num_edges, min_iter, max_iter, min_scaling, max_scaling)
    test_cases = [
        # Small sparse
        (100, 100, 1000, 1000, 2.0, 2.0), # AvgDeg=2 -> Scaling=1.0 -> Min=2.0
        
        # User Case: 1112 nodes, 8586 edges -> AvgDeg ~ 15.4
        # expected iter: 2224
        # expected scaling: 15.4 * 0.5 = 7.7
        (1112, 8586, 2224, 2224, 7.6, 7.8), 
        
        # Dense Small
        (100, 1000, 1000, 1000, 10.0, 10.0), # AvgDeg=20 -> Scaling=10 (Cap)
        
        # Large Sparse
        (2000, 2000, 4000, 4000, 2.0, 2.0), # AvgDeg=2 -> Scaling=1.0 -> Min=2.0
    ]
    
    all_passed = True
    for nodes, edges, min_i, max_i, min_s, max_s in test_cases:
        if not verify_params(nodes, edges, min_i, max_i, min_s, max_s):
            all_passed = False
            
    if all_passed:
        print("\nAll tests PASSED!")
    else:
        print("\nSome tests FAILED!")

if __name__ == "__main__":
    main()
