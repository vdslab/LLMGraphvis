from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app import models
from app.logic import attributes, subgraph
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_db():
    Base.metadata.create_all(bind=engine)
    return SessionLocal()

def reproduce_subgraph_description_issue(db):
    print("\n--- Reproducing Subgraph Description Issue ---")
    # 1. Create Source Network
    network = models.Network(name="Source Network")
    db.add(network)
    db.commit()
    db.refresh(network)
    net_id = network.id

    # 2. Add Attribute with Description
    attr = models.NodeAttribute(
        network_id=net_id, 
        attribute_name="role", 
        data_type="string", 
        description="The role of the node in the organization"
    )
    db.add(attr)
    
    # 3. Add Nodes and Values
    n1 = models.Node(network_id=net_id, node_id="A", label="Alice")
    n2 = models.Node(network_id=net_id, node_id="B", label="Bob")
    db.add_all([n1, n2])
    db.commit()
    db.refresh(attr)
    db.refresh(n1)
    db.refresh(n2)

    val1 = models.NodeAttributeValue(node_id=n1.id, attribute_id=attr.id)
    db.add(val1)
    db.commit()
    val1_text = models.NodeTextAttributeValue(node_attribute_value_id=val1.id, text_value="Manager")
    db.add(val1_text)
    db.commit()

    # 4. Create Subgraph
    print("Creating subgraph...")
    result = subgraph.create_subgraph_from_nodes(net_id, ["A"], db, suffix="Test Subgraph")
    new_net_id = result["new_network_id"]

    # 5. Check New Attribute Description
    new_attr = db.query(models.NodeAttribute).filter(
        models.NodeAttribute.network_id == new_net_id,
        models.NodeAttribute.attribute_name == "role"
    ).first()

    if new_attr:
        print(f"Original Description: '{attr.description}'")
        print(f"Copied Description:   '{new_attr.description}'")
        if new_attr.description != attr.description:
            print("FAILURE: Description was NOT copied!")
        else:
            print("SUCCESS: Description was copied.")
    else:
        print("FAILURE: Attribute not found in subgraph!")

def reproduce_get_node_attributes_issue(db):
    print("\n--- Reproducing get_node_attributes Issue ---")
    # 1. Create Network
    network = models.Network(name="Attr Test Network")
    db.add(network)
    db.commit()
    db.refresh(network)
    net_id = network.id

    # 2. Add Attribute WITHOUT Values initially
    attr = models.NodeAttribute(
        network_id=net_id, 
        attribute_name="age", 
        data_type="float", 
        description="Age of the person"
    )
    db.add(attr)
    db.commit()

    # 3. Call get_attribute_stats
    print("Calling get_attribute_stats for float attribute with NO values...")
    try:
        stats = attributes.get_attribute_stats(
            net_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db
        )
        print("Stats Result:", json.dumps(stats, indent=2))
    except Exception as e:
        print(f"FAILURE: get_attribute_stats raised exception: {e}")
        import traceback
        traceback.print_exc()

    # 4. Add Value and Call Again
    n1 = models.Node(network_id=net_id, node_id="X", label="Xavier")
    db.add(n1)
    db.commit()
    val1 = models.NodeAttributeValue(node_id=n1.id, attribute_id=attr.id)
    db.add(val1)
    db.commit()
    val1_float = models.NodeFloatAttributeValue(node_attribute_value_id=val1.id, float_value=30.0)
    db.add(val1_float)
    db.commit()

    print("Calling get_attribute_stats for float attribute WITH values...")
    try:
        stats = attributes.get_attribute_stats(
            net_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db
        )
        print("Stats Result:", json.dumps(stats, indent=2))
    except Exception as e:
        print(f"FAILURE: get_attribute_stats raised exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    db = setup_db()
    try:
        reproduce_subgraph_description_issue(db)
        reproduce_get_node_attributes_issue(db)
    finally:
        db.close()
