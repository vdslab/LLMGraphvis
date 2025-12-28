import sys
import os

# Add project root to sys.path
api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(api_root)
sys.path.append(project_root)
sys.path.append(api_root)

from app.core import database
from app.logic import subgraph, layout, network_metadata
from common import models

def verify_layout_inheritance():
    print("--- Verifying Subgraph Layout Inheritance ---")
    db = database.SessionLocal()
    try:
        # 1. Create Source Network
        print("1. Creating Source Network...")
        net = models.Network(name="SourceNet", last_layout_name="spring")
        db.add(net)
        db.commit()
        db.refresh(net)
        net_id = net.id

        # 2. Add Nodes with Layout
        print("2. Adding Nodes and Attributes...")
        n1 = models.Node(network_id=net_id, node_id="A", label="A")
        n2 = models.Node(network_id=net_id, node_id="B", label="B")
        db.add_all([n1, n2])
        db.commit()

        # Create Layout Attributes
        from app.logic.attributes import get_or_create_attribute
        attr_x = get_or_create_attribute(net_id, "spring_x", models.NodeAttribute, db, "float")
        attr_y = get_or_create_attribute(net_id, "spring_y", models.NodeAttribute, db, "float")
        
        # Add values (A: 10,10; B: 20,20)
        nav1x = models.NodeAttributeValue(node_id=n1.id, attribute_id=attr_x.id)
        nav1y = models.NodeAttributeValue(node_id=n1.id, attribute_id=attr_y.id)
        nav2x = models.NodeAttributeValue(node_id=n2.id, attribute_id=attr_x.id)
        nav2y = models.NodeAttributeValue(node_id=n2.id, attribute_id=attr_y.id)
        db.add_all([nav1x, nav1y, nav2x, nav2y])
        db.commit()

        val1x = models.NodeFloatAttributeValue(node_attribute_value_id=nav1x.id, float_value=10.0)
        val1y = models.NodeFloatAttributeValue(node_attribute_value_id=nav1y.id, float_value=10.0)
        val2x = models.NodeFloatAttributeValue(node_attribute_value_id=nav2x.id, float_value=20.0)
        val2y = models.NodeFloatAttributeValue(node_attribute_value_id=nav2y.id, float_value=20.0)
        db.add_all([val1x, val1y, val2x, val2y])
        db.commit()

        # 3. Create Subgraph (Preserve Layout)
        print("3. Creating Subgraph (preserve_layout=True)...")
        res = subgraph.create_subgraph_from_nodes(
            source_network_id=net_id,
            node_ids=["A", "B"],
            db=db,
            suffix="WithLayout",
            preserve_layout=True
        )
        
        sub_id = res['new_network_id']
        sub_net = db.query(models.Network).filter(models.Network.id == sub_id).first()
        
        print(f"   Subgraph ID: {sub_id}")
        print(f"   Last Layout Name: {sub_net.last_layout_name}")
        
        if sub_net.last_layout_name != "spring":
            print(f"❌ FAIL: Expected last_layout_name 'spring', got '{sub_net.last_layout_name}'")
        else:
            print("✅ PASS: inherited last_layout_name")

        # Check attributes
        # Need to find the attribute ID for spring_x in the new network
        sub_attr_x = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == sub_id, 
            models.NodeAttribute.attribute_name == "spring_x"
        ).first()

        if not sub_attr_x:
            print("❌ FAIL: 'spring_x' attribute not found in subgraph")
        else:
            print("✅ PASS: 'spring_x' attribute structure exists")
            
            # Check values
            # Simply check count of values
            vals = db.query(models.NodeAttributeValue).filter(
                models.NodeAttributeValue.attribute_id == sub_attr_x.id
            ).all()
            print(f"   Found {len(vals)} values for spring_x (Expected 2)")
            if len(vals) == 2:
                print("✅ PASS: Values copied")
            else:
                 print("❌ FAIL: Value count mismatch")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_layout_inheritance()
