import sys
import os

# Add networkx-api and root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
networkx_api_dir = os.path.abspath(os.path.join(current_dir, ".."))
root_dir = os.path.abspath(os.path.join(networkx_api_dir, ".."))

if networkx_api_dir not in sys.path:
    sys.path.append(networkx_api_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from common import models
# from app.core import database # Not needed for verification script using in-memory DB
from app.logic.centrality import calculate_centrality
from app.logic.visualization_builder import build_visualization
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def verify():
    # Setup in-memory DB
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # 1. Create Network
        network = models.Network(id=1, name="Test Net")
        db.add(network)
        
        # 2. Create Star Graph (n0 is center)
        # n0 will have degree 4, others 1
        nodes = []
        for i in range(5):
            n = models.Node(network_id=1, node_id=f"n{i}")
            db.add(n)
            nodes.append(n)
        db.commit()
        
        node_map = {n.node_id: n.id for n in nodes}
        
        edges = []
        for i in range(1, 5):
            e = models.Edge(
                network_id=1, 
                source_node_id=node_map["n0"], 
                target_node_id=node_map[f"n{i}"],
                edge_id=f"e{i}"
            )
            db.add(e)
        db.commit()

        # 3. Calculate Degree Centrality
        print("Calculating centrality...")
        calculate_centrality(1, "degree", db)

        # 4. Verify Attribute Exists
        attr = db.query(models.NodeAttribute).filter_by(network_id=1, attribute_name="degree_centrality").first()
        if not attr:
            print("FAILURE: degree_centrality attribute not found.")
            return

        # 5. Build Visualization with Node Size mapped to degree_centrality
        print("Building visualization...")
        vis = build_visualization(
            db, 
            network_id=1, 
            node_size_config={
                "attribute": "degree_centrality",
                "min": 10,
                "max": 50
            }
        )

        # 6. Check Sizes
        # n0 should be largest (max=50), others smaller (min=10)
        # Centrality values: n0=1.0 (normalized? nx returns 1.0 for star center if unnormalized? no, degree centrality is normalized)
        # For star graph of 5 nodes:
        # n0 degree = 4, size = 4/(5-1) = 1.0
        # nX degree = 1, size = 1/(5-1) = 0.25
        
        vis_nodes = {n["id"]: n for n in vis["nodes"]}
        
        n0_size = vis_nodes["n0"]["size"]
        n1_size = vis_nodes["n1"]["size"]
        
        print(f"n0 size: {n0_size}")
        print(f"n1 size: {n1_size}")

        if n0_size > n1_size:
            print("SUCCESS: Center node is larger than peripheral nodes.")
            # Ideally n0 should be close to max (50) and n1 close to min (10)
            if abs(n0_size - 50) < 1.0:
                 print("SUCCESS: n0 size is approx 50.")
            else:
                 print(f"WARNING: n0 size {n0_size} is not 50 (expected max).")
                 
            if abs(n1_size - 10) < 1.0:
                 print("SUCCESS: n1 size is approx 10.")
            else:
                 print(f"WARNING: n1 size {n1_size} is not 10 (expected min).")

        else:
            print("FAILURE: Center node is not larger.")

    finally:
        db.close()

if __name__ == "__main__":
    verify()
