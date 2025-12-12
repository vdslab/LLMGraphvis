
import sys
import os

# Add networkx-api to path
sys.path.append(os.path.join(os.getcwd(), "networkx-api"))

from app import models
from app.core import database
from app.logic import subgraph, importer
import networkx as nx

def verify_lcc_logic():
    print("Verifying LCC logic...")
    db = database.SessionLocal()
    try:
        # Create a disconnected graph
        G = nx.Graph()
        G.add_edge("1", "2")
        G.add_edge("2", "3") # Component 1 (Size 3)
        G.add_edge("4", "5") # Component 2 (Size 2)
        
        graphml = "".join(nx.generate_graphml(G))
        
        # Create parent network
        parent_network = models.Network(name="Disconnected Graph", graphml_content=graphml)
        db.add(parent_network)
        db.commit()
        db.refresh(parent_network)
        print(f"Created parent network: {parent_network.id}")
        
        # Parse and save (needed for nodes/edges tables)
        importer.parse_and_save_graphml(parent_network.id, graphml, db)
        
        # Call the logic
        result = subgraph.create_largest_component_subgraph(parent_network.id, db)
        print(f"Result: {result}")
        
        new_network_id = result["new_network_id"]
        
        # Verify the new network has 3 nodes
        new_nodes = db.query(models.Node).filter(models.Node.network_id == new_network_id).all()
        print(f"New network nodes: {[n.node_id for n in new_nodes]}")
        
        if len(new_nodes) == 3:
            print("SUCCESS: Largest component has 3 nodes.")
        else:
            print(f"FAILURE: Expected 3 nodes, got {len(new_nodes)}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_lcc_logic()
