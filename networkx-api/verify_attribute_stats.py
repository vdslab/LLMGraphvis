
import sys
import os
import networkx as nx

# Add current dir to path to import app modules
sys.path.append(os.getcwd())

from app.core import database
from app import models
from app.logic import attributes

def verify():
    db = database.SessionLocal()
    network_id = 99999  # Test ID
    
    try:
        # Cleanup
        attributes._clear_network_data(network_id, db)
        # Delete attribute definitions
        db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id).delete()
        db.query(models.EdgeAttribute).filter(models.EdgeAttribute.network_id == network_id).delete()
        
        # Also ensure network record is gone (since helper doesn't delete network itself)
        db.query(models.Network).filter(models.Network.id == network_id).delete()
        db.commit()
        
        # Setup Test Data
        network = models.Network(id=network_id, name="Test Net", graphml_content="<graphml/>")
        db.add(network)
        db.commit()
        
        # 1. Float Attribute: "weight"
        attr_float = models.NodeAttribute(network_id=network_id, attribute_name="weight", data_type="float")
        db.add(attr_float)
        db.commit()
        db.refresh(attr_float)
        
        # 2. String Attribute: "group"
        attr_str = models.NodeAttribute(network_id=network_id, attribute_name="group", data_type="string")
        db.add(attr_str)
        db.commit()
        db.refresh(attr_str)
        
        # Add Values
        # Float: 1.0, 5.0, 10.0 -> Min 1.0, Max 10.0
        # String: "A", "A", "B" -> Unique 2, Top ["A"]
        
        node = models.Node(network_id=network_id, node_id="n1")
        db.add(node); db.commit(); db.refresh(node)
        
        # Float Values
        val1 = models.NodeAttributeValue(node_id=node.id, attribute_id=attr_float.id)
        db.add(val1); db.commit(); db.refresh(val1)
        db.add(models.NodeFloatAttributeValue(node_attribute_value_id=val1.id, float_value=1.0))
        
        # Validation requires multiple nodes to have meaningful stats, lets make another node
        node2 = models.Node(network_id=network_id, node_id="n2")
        db.add(node2); db.commit(); db.refresh(node2)

        val2 = models.NodeAttributeValue(node_id=node2.id, attribute_id=attr_float.id)
        db.add(val2); db.commit(); db.refresh(val2)
        db.add(models.NodeFloatAttributeValue(node_attribute_value_id=val2.id, float_value=10.0))
        
        # String Values
        val3 = models.NodeAttributeValue(node_id=node.id, attribute_id=attr_str.id)
        db.add(val3); db.commit(); db.refresh(val3)
        db.add(models.NodeTextAttributeValue(node_attribute_value_id=val3.id, text_value="A"))
        
        val4 = models.NodeAttributeValue(node_id=node2.id, attribute_id=attr_str.id)
        db.add(val4); db.commit(); db.refresh(val4)
        db.add(models.NodeTextAttributeValue(node_attribute_value_id=val4.id, text_value="B"))
        
        # Node 3 for repetition
        node3 = models.Node(network_id=network_id, node_id="n3")
        db.add(node3); db.commit(); db.refresh(node3)
        
        val5 = models.NodeAttributeValue(node_id=node3.id, attribute_id=attr_str.id)
        db.add(val5); db.commit(); db.refresh(val5)
        db.add(models.NodeTextAttributeValue(node_attribute_value_id=val5.id, text_value="A"))
        
        db.commit()
        
        # Call Helper
        stats = attributes.get_attribute_stats(
            network_id, 
            models.NodeAttribute, 
            models.NodeAttributeValue, 
            models.NodeFloatAttributeValue, 
            models.NodeTextAttributeValue, 
            db
        )
        
        print("Result:", stats)
        
        # Verification
        float_stat = next(s for s in stats if s['name'] == 'weight')
        assert float_stat['stats']['min'] == 1.0
        assert float_stat['stats']['max'] == 10.0
        
        str_stat = next(s for s in stats if s['name'] == 'group')
        assert str_stat['stats']['unique_count'] == 2
        assert 'A' in str_stat['stats']['top_values']
        
        print("VERIFICATION PASSED")
        
    except Exception as e:
        print("VERIFICATION FAILED", e)
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        # Cleanup
        try:
            attributes._clear_network_data(network_id, db)
            db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id).delete()
            db.query(models.EdgeAttribute).filter(models.EdgeAttribute.network_id == network_id).delete()
            db.query(models.Network).filter(models.Network.id == network_id).delete()
            db.commit()
        except:
            pass
        db.close()

if __name__ == "__main__":
    verify()
