import sys
import os
import math

# Add networkx-api and root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
networkx_api_dir = os.path.abspath(os.path.join(current_dir, ".."))
root_dir = os.path.abspath(os.path.join(networkx_api_dir, ".."))

if networkx_api_dir not in sys.path:
    sys.path.append(networkx_api_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from common import models
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
        print("1. Creating dummy network with 100 nodes...")
        network = models.Network(id=1, name="Test Net")
        db.add(network)
        db.flush()

        # Add node stats data
        attr = models.NodeAttribute(network_id=1, attribute_name="score", data_type="float")
        db.add(attr)
        
        # Add layout attrs
        attr_x = models.NodeAttribute(network_id=1, attribute_name="forceatlas2_x", data_type="float")
        attr_y = models.NodeAttribute(network_id=1, attribute_name="forceatlas2_y", data_type="float")
        db.add(attr_x)
        db.add(attr_y)
        
        db.commit() # Commit to get IDs

        for i in range(100):
            n = models.Node(network_id=1, node_id=f"n{i}", label=f"Node {i}")
            db.add(n)
            db.flush() # Need n.id

            # Score
            nav = models.NodeAttributeValue(node_id=n.id, attribute_id=attr.id)
            db.add(nav)
            db.flush()
            db.add(models.NodeFloatAttributeValue(node_attribute_value_id=nav.id, float_value=float(i)))
            
            # Layout X
            nav_x = models.NodeAttributeValue(node_id=n.id, attribute_id=attr_x.id)
            db.add(nav_x)
            db.flush()
            db.add(models.NodeFloatAttributeValue(node_attribute_value_id=nav_x.id, float_value=0.0))

            # Layout Y
            nav_y = models.NodeAttributeValue(node_id=n.id, attribute_id=attr_y.id)
            db.add(nav_y)
            db.flush()
            db.add(models.NodeFloatAttributeValue(node_attribute_value_id=nav_y.id, float_value=0.0))

        db.commit()

        print("2. Testing Default Scaling (Factor=1.0)...")
        vis_default = build_visualization(
            db, 
            network_id=1, 
            node_size_config={
                "attribute": "score",
                # min/max will be adaptive
            }
        )
        
        node_sizes = [n["size"] for n in vis_default["nodes"]]
        if not node_sizes:
            print("FAILURE: No nodes returned in visualization.")
            return

        avg_size_1 = sum(node_sizes) / len(node_sizes)
        print(f"Avg Size (Factor 1.0): {avg_size_1:.2f}")

        # Check if adaptive logic is working (should be around 115 for 100 nodes?)
        # Base for 100 nodes = 600/10 = 60.
        # Min=30, Max=150. Avg=(30+150)/2 = 90.
        if 80 < avg_size_1 < 100:
             print("SUCCESS: Default adaptive sizing is within expected range (approx 90).")
        else:
             print(f"WARNING: Default adaptive sizing might be off. Expected ~90, got {avg_size_1:.2f}")

        print("3. Testing Scaling Factor = 2.0...")
        vis_2x = build_visualization(
            db, 
            network_id=1, 
            node_size_config={
                "attribute": "score",
                "scaling_factor": 2.0
            }
        )
        node_sizes_2x = [n["size"] for n in vis_2x["nodes"]]
        avg_size_2 = sum(node_sizes_2x) / len(node_sizes_2x)
        print(f"Avg Size (Factor 2.0): {avg_size_2:.2f}")

        ratio_2 = avg_size_2 / avg_size_1
        print(f"Ratio 2.0/1.0: {ratio_2:.2f}")
        
        if abs(ratio_2 - 2.0) < 0.1:
            print("SUCCESS: Scaling factor 2.0 worked.")
        else:
            print("FAILURE: Scaling factor 2.0 did not double the sizes.")

        print("4. Testing Scaling Factor = 0.5...")
        vis_half = build_visualization(
            db, 
            network_id=1, 
            node_size_config={
                "attribute": "score",
                "scaling_factor": 0.5
            }
        )
        node_sizes_half = [n["size"] for n in vis_half["nodes"]]
        avg_size_half = sum(node_sizes_half) / len(node_sizes_half)
        print(f"Avg Size (Factor 0.5): {avg_size_half:.2f}")

        ratio_half = avg_size_half / avg_size_1
        print(f"Ratio 0.5/1.0: {ratio_half:.2f}")

        if abs(ratio_half - 0.5) < 0.1:
            print("SUCCESS: Scaling factor 0.5 worked.")
        else:
            print("FAILURE: Scaling factor 0.5 did not halve the sizes.")

    finally:
        db.close()

if __name__ == "__main__":
    verify()
