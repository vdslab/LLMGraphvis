
import sys
import os

# Add parent directory to path to allow importing modules
sys.path.append(os.path.join(os.path.dirname(__file__), "networkx-api"))

import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from common import models
from common.models import Base
from app.logic import centrality
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
    # Create a star graph: Center 0, Leaves 1-5
    network = models.Network(name="Test Centrality Graph")
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

    # Create map of node_id (str) -> id (int) (PK)
    node_pk_map = {}
    for node in nodes:
        node_pk_map[node.node_id] = node.id

    # Edges: All connect to 0
    for i in range(1, 6):
        # We want edge from "0" to "i" (string IDs)
        # But we must store PKs in source_node_id/target_node_id
        u_pk = node_pk_map["0"]
        v_pk = node_pk_map[str(i)]
        
        edge = models.Edge(
            network_id=network.id, 
            edge_id=f"e0-{i}",
            source_node_id=u_pk, 
            target_node_id=v_pk
        )
        db.add(edge)
    db.commit()
    return network.id

def verify_centrality_logic():
    cleanup()
    init_db()
    db = TestingSessionLocal()
    
    try:
        print("Creating test network (Star graph)...")
        network_id = create_test_network(db)
        
        print("Calculating degree centrality...")
        # Should return a dict of {node_id: score}
        scores = centrality.calculate_centrality(network_id, "degree", db)
        print(f"Calculated scores: {scores}")
        
        # Verify Center Node has highest centrality
        assert scores["0"] > scores["1"]
        
        # Verify Database Persistence
        print("Verifying DB Persistence...")
        attr_name = "degree_centrality"
        
        attr = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.attribute_name == attr_name
        ).first()
        
        if not attr:
            print(f"FAILED: Attribute '{attr_name}' not found.")
            return

        print(f"Attribute ID: {attr.id}, Type: {attr.data_type}")
        assert attr.data_type == "float"

        # Verify Values
        # Join NodeAttributeValue -> NodeFloatAttributeValue
        values = db.query(models.NodeFloatAttributeValue).join(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.attribute_id == attr.id
        ).all()
        
        print(f"Found {len(values)} centrality values stored.")
        assert len(values) == 6
        
        print("Verification PASSED: Centrality calculation and bulk save logic works.")
        
    except Exception as e:
        print(f"Verification FAILED with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        cleanup()

if __name__ == "__main__":
    verify_centrality_logic()
