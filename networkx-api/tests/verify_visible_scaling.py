
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
from app.logic.visualization_builder import VisualizationBuilder
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def verify():
    # Setup in-memory DB
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        print("1. Creating dummy network with 1000 nodes...")
        network = models.Network(id=1, name="Scale Test Net")
        db.add(network)
        db.flush()

        # Define attributes
        attr_x = models.NodeAttribute(network_id=1, attribute_name="forceatlas2_x", data_type="float")
        attr_y = models.NodeAttribute(network_id=1, attribute_name="forceatlas2_y", data_type="float")
        db.add(attr_x)
        db.add(attr_y)
        db.commit() # Commit to get IDs

        # Add nodes
        for i in range(1000):
            n = models.Node(network_id=1, node_id=f"n{i}", label=f"Node {i}")
            db.add(n)
            db.flush() # Need n.id
            
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

        print("2. Configuring context to show only 50 nodes...")
        # We will set context_config={"visible": False}, and define focus_network_id=None
        # Wait, visualization_builder logic:
        # if not is_focused and context_config.visible is False: continue
        # This means we need to mark some nodes as 'focused' to make them visible?
        # OR we can't easily specify "some nodes visible, some not" via context_config alone without a focus/subgraph context.
        # However, the standard Logic flow usually involves a focus_network_id (subgraph) to define 'is_focused'.
        
        # Let's create a dummy subgraph network (ID 2) with 50 nodes to act as the "focus".
        subgraph = models.Network(id=2, name="Focus Subgraph")
        db.add(subgraph)
        db.flush()
        
        # Add mappping to focus_node_map (mocking it)
        # VisualizationBuilder._get_focus_node_map queries DB.
        # We need to insert relationships or mock the method.
        # It's easier to verify using the real DB query logic.
        # But VisualizationBuilder logic for focus map is: 
        # self.focus_node_map = self._get_focus_node_map(self.focus_network_id)
        # _get_focus_node_map returns {node_id_str: db_id} for nodes in focus network.
        
        for i in range(50):
            # These 50 nodes are in the subgraph
            sn = models.Node(network_id=2, node_id=f"n{i}", label=f"SubNode {i}")
            db.add(sn)
        db.commit()

        # Now instantiate builder
        print("3. Building Visualization with Focus...")
        builder = VisualizationBuilder(
            network_id=1, # Main network (1000 nodes)
            db=db,
            focus_network_id=2, # Focus on subgraph (50 nodes)
            context_config={"visible": False} # Hide everything else
        )
        
        # Prepare
        builder.validate_and_prepare()
        builder.fetch_data()
        builder.calculate_statistics()
        
        # Build
        vis_data = builder.build()
        nodes = vis_data["nodes"]
        
        print(f"Visible Nodes Count: {len(nodes)}")
        if len(nodes) != 50:
            print(f"FAILURE: Expected 50 visible nodes, got {len(nodes)}")
            return

        # Check sizes
        sizes = [n["size"] for n in nodes]
        avg_size = sum(sizes) / len(sizes)
        print(f"Average Size: {avg_size:.2f}")
        
        # Expected:
        # If counting 1000 nodes: 600/sqrt(1000)=19. Max(5,19)=19. Default = ~38.
        # If counting 50 nodes:   600/sqrt(50)=85.  Max(5,85)=85. Default = ~170.
        
        if avg_size > 100:
            print("SUCCESS: Node sizes are large (~170), indicating adaptation to VISIBLE count.")
        elif avg_size < 50:
            print("FAILURE: Node sizes are small (~38), indicating adaptation to TOTAL count.")
        else:
            print(f"WARNING: Size {avg_size} is ambiguous.")

    finally:
        db.close()

if __name__ == "__main__":
    verify()
