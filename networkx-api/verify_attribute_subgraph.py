import sys
import os
import requests
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.abspath("/Users/takuma/develop/vdslab/master/GraphVisAgent/networkx-api"))

from app import models
from app.core import database
from app.logic import filter
from app.schemas.filter import AttributeCondition, Range

# Setup Database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_verification.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

def setup_test_data(db):
    # Create Network
    network = models.Network(name="Test Network", graphml_content="")
    db.add(network)
    db.commit()
    db.refresh(network)
    network_id = network.id
    
    # Attributes
    attr_age = models.NodeAttribute(network_id=network_id, attribute_name="Age", data_type="float")
    attr_gender = models.NodeAttribute(network_id=network_id, attribute_name="Gender", data_type="string")
    db.add_all([attr_age, attr_gender])
    db.commit()
    
    # Nodes & Values
    # Node 1: Age 15, Gender M
    n1 = models.Node(network_id=network_id, node_id="n1", label="User1")
    db.add(n1)
    db.commit()
    db.add(models.NodeAttributeValue(node_id=n1.id, attribute_id=attr_age.id, float_value=models.NodeFloatAttributeValue(float_value=15.0)))
    db.add(models.NodeAttributeValue(node_id=n1.id, attribute_id=attr_gender.id, text_value=models.NodeTextAttributeValue(text_value="M")))
    
    # Node 2: Age 25, Gender F
    n2 = models.Node(network_id=network_id, node_id="n2", label="User2")
    db.add(n2)
    db.commit()
    db.add(models.NodeAttributeValue(node_id=n2.id, attribute_id=attr_age.id, float_value=models.NodeFloatAttributeValue(float_value=25.0)))
    db.add(models.NodeAttributeValue(node_id=n2.id, attribute_id=attr_gender.id, text_value=models.NodeTextAttributeValue(text_value="F")))

    # Node 3: Age 10, Gender F
    n3 = models.Node(network_id=network_id, node_id="n3", label="User3")
    db.add(n3)
    db.commit()
    db.add(models.NodeAttributeValue(node_id=n3.id, attribute_id=attr_age.id, float_value=models.NodeFloatAttributeValue(float_value=10.0)))
    db.add(models.NodeAttributeValue(node_id=n3.id, attribute_id=attr_gender.id, text_value=models.NodeTextAttributeValue(text_value="F")))
    
    # Node 4: Age 40, Gender M
    n4 = models.Node(network_id=network_id, node_id="n4", label="User4")
    db.add(n4)
    db.commit()
    db.add(models.NodeAttributeValue(node_id=n4.id, attribute_id=attr_age.id, float_value=models.NodeFloatAttributeValue(float_value=40.0)))
    db.add(models.NodeAttributeValue(node_id=n4.id, attribute_id=attr_gender.id, text_value=models.NodeTextAttributeValue(text_value="M")))

    db.commit()
    return network_id

def verify_filtering():
    db = SessionLocal()
    try:
        network_id = setup_test_data(db)
        print(f"Created Test Network ID: {network_id}")
        
        # Test 1: Range (Age 12-30) -> Should match n1 (15), n2 (25)
        print("\nTest 1: Range (Age 12-30)")
        cond1 = AttributeCondition(
            attribute_name="Age",
            ranges=[Range(min=12, max=30)]
        )
        res1 = filter.create_subgraph_by_filter(network_id, [cond1], "Test1", db)
        sub1 = db.query(models.Network).filter(models.Network.id == res1["new_network_id"]).first()
        nodes1 = db.query(models.Node).filter(models.Node.network_id == sub1.id).all()
        ids1 = sorted([n.node_id for n in nodes1])
        print(f"Result: {ids1}")
        assert ids1 == ["n1", "n2"]
        
        # Test 2: Category (Gender F) -> Should match n2 (F), n3 (F)
        print("\nTest 2: Category (Gender F)")
        cond2 = AttributeCondition(
            attribute_name="Gender",
            categories=["F"]
        )
        res2 = filter.create_subgraph_by_filter(network_id, [cond2], "Test2", db)
        sub2 = db.query(models.Network).filter(models.Network.id == res2["new_network_id"]).first()
        nodes2 = db.query(models.Node).filter(models.Node.network_id == sub2.id).all()
        ids2 = sorted([n.node_id for n in nodes2])
        print(f"Result: {ids2}")
        assert ids2 == ["n2", "n3"]
        
        # Test 3: Mixed (Age 10-20 AND Gender F) -> Should match n3 (10, F) only (n1 is M, n2 is 25)
        print("\nTest 3: Mixed (Age 10-20 AND Gender F)")
        # Note: Age 10 is on boundary, implementation uses <= and >= so it should be included
        cond3_age = AttributeCondition(attribute_name="Age", ranges=[Range(min=10, max=20)])
        cond3_gen = AttributeCondition(attribute_name="Gender", categories=["F"])
        
        res3 = filter.create_subgraph_by_filter(network_id, [cond3_age, cond3_gen], "Test3", db)
        sub3 = db.query(models.Network).filter(models.Network.id == res3["new_network_id"]).first()
        nodes3 = db.query(models.Node).filter(models.Node.network_id == sub3.id).all()
        ids3 = sorted([n.node_id for n in nodes3])
        print(f"Result: {ids3}")
        assert ids3 == ["n3"]

        # Test 4: Multiple Ranges (Age < 12 OR Age > 30) -> n3 (10), n4 (40)
        print("\nTest 4: Multiple Ranges (Age < 12 OR Age > 30)")
        cond4 = AttributeCondition(
            attribute_name="Age",
            ranges=[Range(max=11.9), Range(min=30.1)]
        )
        res4 = filter.create_subgraph_by_filter(network_id, [cond4], "Test4", db)
        sub4 = db.query(models.Network).filter(models.Network.id == res4["new_network_id"]).first()
        nodes4 = db.query(models.Node).filter(models.Node.network_id == sub4.id).all()
        ids4 = sorted([n.node_id for n in nodes4])
        print(f"Result: {ids4}")
        assert ids4 == ["n3", "n4"]

        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nTest Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        db.close()
        if os.path.exists("test_verification.db"):
            os.remove("test_verification.db")

if __name__ == "__main__":
    verify_filtering()
