import asyncio
import os
from app.services import network_service
from app.core.database import SessionLocal
from app import models

# Mock data
GRAPHML_DATA = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <node id="n2"/>
    <node id="n3"/>
    <edge source="n0" target="n1"/>
    <edge source="n1" target="n2"/>
    <edge source="n2" target="n3"/>
    <edge source="n3" target="n0"/>
  </graph>
</graphml>
"""

async def verify_layout():
    print("Starting Layout Verification...")
    
    # 1. Initialize Network
    print("\n1. Initializing Network...")
    # Create a dummy network ID (we might need to actually create a chat/network in DB if we were strictly following flow, 
    # but network_service.initialize_network just sends to API)
    # However, networkx-api needs to save to its DB.
    # Let's use a random ID.
    network_id = 99999 
    
    try:
        await network_service.initialize_network(network_id, GRAPHML_DATA)
        print("Network initialized.")
    except Exception as e:
        print(f"Initialization failed: {e}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        return

    # 2. Calculate Circular Layout
    print("\n2. Calculating Circular Layout...")
    try:
        result = await network_service.calculate_layout(network_id, "circular")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Layout calculation failed: {e}")
        return

    # 3. Generate Visualization with Circular Layout
    print("\n3. Generating Visualization (Circular)...")
    try:
        vis_data = await network_service.generate_visualization(network_id, {"layout_name": "circular"})
        nodes = vis_data.get("nodes", [])
        print(f"Got {len(nodes)} nodes.")
        if nodes:
            print(f"Sample Node: {nodes[0]}")
            # Check if x, y are present
            if "x" in nodes[0] and "y" in nodes[0]:
                print("SUCCESS: Coordinates present.")
            else:
                print("FAILURE: Coordinates missing.")
    except Exception as e:
        print(f"Visualization generation failed: {e}")
        return

    # 4. Calculate Spring Layout
    print("\n4. Calculating Spring Layout...")
    try:
        result = await network_service.calculate_layout(network_id, "spring")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Layout calculation failed: {e}")
        return

    # 5. Generate Visualization with Spring Layout
    print("\n5. Generating Visualization (Spring)...")
    try:
        vis_data = await network_service.generate_visualization(network_id, {"layout_name": "spring"})
        nodes = vis_data.get("nodes", [])
        if nodes:
            print(f"Sample Node: {nodes[0]}")
            # We can't easily check if coords changed without comparing, but successful return is good enough for now.
            print("SUCCESS: Spring layout visualization generated.")
    except Exception as e:
        print(f"Visualization generation failed: {e}")
        return

if __name__ == "__main__":
    asyncio.run(verify_layout())
