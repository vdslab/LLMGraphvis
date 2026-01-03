
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import networkx as nx
from app.logic.layout import determine_layout_params

def verify_params(num_nodes, expected_iter_min, expected_iter_max):
    G = nx.Graph()
    G.add_nodes_from(range(num_nodes))
    
    params = determine_layout_params(G, "forceatlas2")
    
    max_iter = params["max_iter"]
    print(f"Nodes: {num_nodes}, max_iter: {max_iter}")
    
    if not (expected_iter_min <= max_iter <= expected_iter_max):
        print(f"FAIL: max_iter {max_iter} not in range [{expected_iter_min}, {expected_iter_max}]")
        return False
        
    if params["jitter_tolerance"] != 1.0:
         print(f"FAIL: jitter_tolerance is {params['jitter_tolerance']}, expected 1.0")
         return False

    return True

def main():
    print("Verifying ForceAtlas2 Dynamic Scaling...")
    
    # Test cases: (num_nodes, min_iter, max_iter)
    test_cases = [
        (100, 1000, 1000),    # Small: Should be floor 1000
        (400, 1000, 1000),    # Small: Should be floor 1000
        (500, 1000, 1000),    # Edge case: max(1000, 1000) = 1000
        (600, 1200, 1200),    # Medium: 600 * 2 = 1200
        (1112, 2224, 2224),   # User Case: 1112 * 2 = 2224
        (2000, 4000, 4000),   # Large: 2000 * 2 = 4000
        (3000, 5000, 5000),   # Very Large: 6000 -> Cap 5000
        (10000, 5000, 5000)   # Huge: Cap 5000
    ]
    
    all_passed = True
    for nodes, min_i, max_i in test_cases:
        if not verify_params(nodes, min_i, max_i):
            all_passed = False
            
    if all_passed:
        print("\nAll tests PASSED!")
    else:
        print("\nSome tests FAILED!")

if __name__ == "__main__":
    main()
