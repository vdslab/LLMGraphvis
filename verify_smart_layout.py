import requests
import json
import time

BASE_URL = "http://localhost:8001/tools"

def verify_smart_layout(network_id, layout_name):
    print(f"Testing layout '{layout_name}' for network {network_id}...")
    
    # 1. Check if attributes exist (using list_node_attributes)
    resp = requests.get(f"{BASE_URL}/list_node_attributes?network_id={network_id}")
    if resp.status_code != 200:
        print(f"Failed to list attributes: {resp.text}")
        return
        
    attrs = resp.json()
    attr_names = [a['name'] for a in attrs]
    x_attr = f"{layout_name}_x"
    y_attr = f"{layout_name}_y"
    
    print(f"Before call: {x_attr} in attributes? {x_attr in attr_names}")
    
    # 2. Call generate_visualization
    payload = {
        "network_id": network_id,
        "layout_name": layout_name,
        "node_size_config": {"attribute": "degree_centrality"},  # Basic config
        "node_color_config": {"attribute": "community", "scale_type": "CATEGORICAL"}
    }
    
    print("Calling generate_visualization...")
    start_time = time.time()
    resp = requests.post(f"{BASE_URL}/generate_visualization", json=payload)
    duration = time.time() - start_time
    
    if resp.status_code == 200:
        data = resp.json()
        nodes = data.get("nodes", [])
        if nodes:
            # Check coordinates of first node
            n = nodes[0]
            print(f"First node coords: ({n.get('x')}, {n.get('y')})")
            
            # Verify they are not default 0.5 if calculation happened
            if n.get('x') != 0.5 or n.get('y') != 0.5:
                print("SUCCESS: Layout seems to have been calculated and applied.")
            else:
                print("WARNING: Coordinates are 0.5. Layout might have failed or not run.")
        else:
            print("No nodes returned.")
    else:
        print(f"Error calling generate_visualization: {resp.status_code} - {resp.text}")

    # 3. Check attributes again
    resp = requests.get(f"{BASE_URL}/list_node_attributes?network_id={network_id}")
    attrs = resp.json()
    attr_names = [a['name'] for a in attrs]
    print(f"After call: {x_attr} in attributes? {x_attr in attr_names}")

if __name__ == "__main__":
    # Use a likely network ID, e.g., 4 or 5 based on logs
    verify_smart_layout(4, "circular")
    print("-" * 20)
    verify_smart_layout(4, "shell")
