import networkx as nx
import sys

print(f"NetworkX version: {nx.__version__}")

try:
    if hasattr(nx, 'forceatlas2_layout'):
        print("SUCCESS: nx.forceatlas2_layout exists.")
        # Try a small run
        G = nx.path_graph(5)
        pos = nx.forceatlas2_layout(G, max_iter=10)
        print("SUCCESS: Simulation ran.")
    else:
        print("FAILURE: nx.forceatlas2_layout does not exist directly.")
        # Check if it's in drawing.layout
        import networkx.drawing.layout as layout
        if hasattr(layout, 'forceatlas2_layout'):
             print("SUCCESS: It is in networkx.drawing.layout.forceatlas2_layout")
        else:
             print("FAILURE: Not found in drawing.layout either.")

except Exception as e:
    print(f"ERROR: {e}")
