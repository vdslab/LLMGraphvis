import logging
import sys

# Configure logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock MCP and Database for unit-like testing of tools.py
# This avoids needing a full running MCP client but tests the logic + decorator
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core import database
from common import models
from app.mcp import tools

def test_list_networks():
    print("\n--- Testing list_networks ---")
    
    # 1. Create a dummy network directly in DB
    db = database.SessionLocal()
    try:
        net = models.Network(name="Test Net 1", description="Created by verification script")
        db.add(net)
        db.commit()
        db.refresh(net)
        print(f"Created test network: {net.id}")
    finally:
        db.close()

    # 2. Call the tool
    try:
        result = tools.list_networks(limit=10)
        print(f"Tool Result: {result}")
        
        # Verify structure
        if "networks" in result:
            networks = result["networks"]
            print(f"Found {len(networks)} networks.")
            found = False
            for n in networks:
                if n["name"] == "Test Net 1":
                    found = True
                    break
            if found:
                print("SUCCESS: Found the test network.")
            else:
                print("FAILURE: Did not find test network.")
        else:
            print("FAILURE: Result missing 'networks' key.")
            
    except Exception as e:
        print(f"FAILURE: Tool raised exception: {e}")

def test_error_handling():
    print("\n--- Testing error handling (via calculate_centrality with invalid ID) ---")
    # Call a tool with invalid ID to trigger exception
    # Safe decorator should catch it and return {"error": ...}
    
    result = tools.calculate_centrality(network_id=999999, centrality_type="degree")
    print(f"Tool Result: {result}")
    
    if isinstance(result, dict) and "error" in result:
        print("SUCCESS: Tool returned error dict as expected.")
        print(f"Error message: {result['error']}")
    else:
        print("FAILURE: Tool did not return error dict.")

if __name__ == "__main__":
    test_list_networks()
    test_error_handling()
