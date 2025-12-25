import networkx as nx
import sys

def check_layout_availability():
    print(f"NetworkX version: {nx.__version__}")
    
    G = nx.complete_graph(10)
    
    print("Testing spring_layout...")
    try:
        nx.spring_layout(G)
        print("spring_layout: OK")
    except Exception as e:
        print(f"spring_layout: FAILED ({e})")

    print("Testing forceatlas2_layout...")
    try:
        if hasattr(nx, 'forceatlas2_layout'):
            # Mimic the call in layout.py
            nx.forceatlas2_layout(G, max_iter=700, scaling_ratio=100.0, seed=42)
            print("forceatlas2_layout: OK")
        else:
            print("forceatlas2_layout: NOT FOUND (AttributeError would be raised in app)")
    except Exception as e:
        print(f"forceatlas2_layout: FAILED ({e})")

if __name__ == "__main__":
    check_layout_availability()
