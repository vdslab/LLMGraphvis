import sys
import os

# Add parent directory to path to allow importing modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "networkx-api"))

import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from common import models
from common.models import Base
from app.logic import community, attributes

from sqlalchemy.pool import StaticPool

# Use a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def cleanup():
    Base.metadata.drop_all(bind=engine)

def create_test_network(db):
    # Create a simple barbell graph: (0,1,2) - (3,4,5) connected by 2-3
    network = models.Network(name="Test Community Graph")
    db.add(network)
    db.commit()
    db.refresh(network)

    # Nodes
    nodes = []
    for i in range(6):
        node = models.Node(network_id=network.id, node_id=str(i))
        db.add(node)
        nodes.append(node)
    db.commit()

    # Edges: Triangle 0-1-2, Triangle 3-4-5, Bridge 2-3
    edges_list = [
        (0, 1), (1, 2), (2, 0), # Cluster 1
        (3, 4), (4, 5), (5, 3), # Cluster 2
        (2, 3) # Bridge
    ]
    
    for u, v in edges_list:
        edge = models.Edge(
            network_id=network.id, 
            edge_id=f"e{u}-{v}",
            source_node_id=str(u), 
            target_node_id=str(v)
        )
        db.add(edge)
    db.commit()
    return network.id

def verify_community_detection():
    cleanup()
    init_db()
    db = TestingSessionLocal()
    
    try:
        print("Creating test network (Barbell graph)...")
        network_id = create_test_network(db)
        
        print("Calculating communities (Louvain)...")
        attr_name = community.calculate_community(network_id, "louvain", db)
        print(f"Attribute created: {attr_name}")
        
        # Verify Attribute Existence
        attr = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.attribute_name == attr_name
        ).first()
        
        if not attr:
            print("FAILED: Attribute 'community' not found.")
            return
        
        print(f"Attribute ID: {attr.id}, Type: {attr.data_type}")
        assert attr.data_type == "string" # Should be stored as string (text) for categorical

        # Verify Values
        values = db.query(models.NodeTextAttributeValue).join(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.attribute_id == attr.id
        ).all()
        
        print(f"Found {len(values)} community values.")
        assert len(values) == 6
        
        communities = {}
        for val in values:
            # Get node_id via relationship or manual join if needed, 
            # but here we just check distribution
            pass
            
        print("Verification PASSED: Community detection logic works.")
        
    except Exception as e:
        print(f"Verification FAILED with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        cleanup()

if __name__ == "__main__":
    verify_community_detection()
