import sys
import os
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8001/api/v1"

def verify_node_search():
    logger.info("Starting Node Search Verification")
    
    # 1. Initialize a simple network
    logger.info("Initializing Network...")
    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="role" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="n1">
      <data key="d0">protagonist</data>
    </node>
    <node id="n2">
      <data key="d0">antagonist</data>
    </node>
    <node id="n3">
       <data key="d0">support</data>
    </node>
    <edge source="n1" target="n2"/>
  </graph>
</graphml>"""
    
    network_id = 9999
    
    try:
        response = requests.post(
            f"{BASE_URL}/networks/initialize",
            json={"network_id": network_id, "graphml_data": graphml}
        )
        response.raise_for_status()
        logger.info(f"Network {network_id} initialized.")
        
        # 2. Search by ID (default)
        logger.info("Testing Search by ID (query='n1')...")
        search_res = requests.get(f"{BASE_URL}/networks/{network_id}/nodes/search", params={"q": "n1"})
        search_res.raise_for_status()
        results = search_res.json()
        logger.info(f"Results: {results}")
        
        assert len(results) > 0, "Should find 'n1'"
        assert results[0]["id"] == "n1", "First result should be 'n1'"
        
        # 3. Search by Attribute
        logger.info("Testing Search by Attribute 'role' (query='prota')...")
        search_res = requests.get(
            f"{BASE_URL}/networks/{network_id}/nodes/search", 
            params={"q": "prota", "attribute": "role"}
        )
        search_res.raise_for_status()
        results = search_res.json()
        logger.info(f"Results: {results}")
        
        assert len(results) > 0, "Should find 'n1' (protagonist)"
        assert results[0]["id"] == "n1", "Found result should be 'n1'"
        assert results[0]["match"] == "protagonist", "Match value should be 'protagonist'"

        # 4. Search Non-existent
        logger.info("Testing Search Non-existent...")
        search_res = requests.get(f"{BASE_URL}/networks/{network_id}/nodes/search", params={"q": "xyz"})
        results = search_res.json()
        assert len(results) == 0, "Should find nothing"

        logger.info("Verification Passed Successfully!")
        
    except Exception as e:
        logger.error(f"Verification Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_node_search()
