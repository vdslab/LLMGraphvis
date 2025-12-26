import sys
import os

# Ensure we can import app and common
# app is in current dir
sys.path.append(os.getcwd())
# common is in parent dir
sys.path.append(os.path.dirname(os.getcwd()))

from app.core import database
from common import models
from app.logic import filter as filter_logic
from app.logic import search as search_logic
from app.schemas.filter import AttributeCondition, Range

def test_filter():
    db = database.SessionLocal()
    try:
        # 1. Find or Create a Network
        network = db.query(models.Network).first()
        if not network:
            print("No network found. Please initialize a network first.")
            return

        network_id = network.id
        print(f"Using Network ID: {network_id}")

        # 2. Inspect available attributes
        attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id).all()
        print(f"Available attributes: {[a.attribute_name for a in attrs]}")

        if not attrs:
            print("No attributes found on this network.")
            return
            
        # Try to find 'nationality' or fallback to others
        target_attrs = [a for a in attrs if a.attribute_name == 'nationality']
        if target_attrs:
            target_attr = target_attrs[0]
        else:
            # Fallback to any text attribute if possible, or just the first one
            target_attr = attrs[0]

        attr_name = target_attr.attribute_name
        print(f"Testing filter on attribute: {attr_name}")

        # 3. Test filter_nodes (get_nodes_by_filter)
        # We'll just look for ANY value matching the first node's value for this attribute
        first_val_query = (
            db.query(models.NodeTextAttributeValue.text_value)
            .join(models.NodeAttributeValue)
            .filter(models.NodeAttributeValue.attribute_id == target_attr.id)
            .first()
        )
        
        if first_val_query:
            val = first_val_query[0]
            print(f"Filtering for {attr_name} == '{val}'")
            
            condition = AttributeCondition(
                attribute_name=attr_name,
                categories=[val]
            )
            
            nodes = filter_logic.get_nodes_by_filter(network_id, [condition], db)
            print(f"Found {len(nodes)} nodes matching condition.")
            if nodes:
                print(f"Sample: {nodes[0]}")
                
                # 4. Test get_node_details
                test_node_id = nodes[0]['id'] # String ID
                print(f"Fetching details for node: {test_node_id}")
                details = search_logic.get_node_details(network_id, test_node_id, db)
                print("Node Details:")
                print(details)
                
                # Check if attributes are present
                assert details is not None
                assert 'attributes' in details
                assert attr_name in details['attributes']
                print("Verification Successful!")
        else:
             print("No text values found for this attribute to test.")

    finally:
        db.close()

if __name__ == "__main__":
    test_filter()
