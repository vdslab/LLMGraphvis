import requests
import sys
import time
import json

BASE_URL = "http://localhost:8000"
NX_API_URL = "http://localhost:8001"
USERNAME = "verify_attr_user"
PASSWORD = "password123"

# Test GraphML with various attributes
TEST_GRAPHML = """<?xml version='1.0' encoding='utf-8'?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d_n_str" for="node" attr.name="test_str_attr" attr.type="string"/>
  <key id="d_n_int" for="node" attr.name="test_int_attr" attr.type="int"/>
  <key id="d_n_float" for="node" attr.name="test_float_attr" attr.type="double"/>
  <key id="d_e_str" for="edge" attr.name="test_edge_str" attr.type="string"/>
  <key id="d_e_float" for="edge" attr.name="test_edge_float" attr.type="double"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d_n_str">value1</data>
      <data key="d_n_int">10</data>
      <data key="d_n_float">1.5</data>
    </node>
    <node id="n1">
      <data key="d_n_str">value2</data>
      <data key="d_n_int">20</data>
      <data key="d_n_float">2.5</data>
    </node>
    <edge source="n0" target="n1">
      <data key="d_e_str">edge_val</data>
      <data key="d_e_float">0.5</data>
    </edge>
  </graph>
</graphml>
"""

def run_verification():
    # 1. Register/Login
    print(f"Registering/Logging in user {USERNAME}...")
    requests.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    resp = requests.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Chat
    print("Creating chat...")
    resp = requests.post(f"{BASE_URL}/chat", headers=headers, json={"name": "Attribute Test Chat"})
    if resp.status_code not in [200, 201]:
        print(f"Create chat failed: {resp.text}")
        sys.exit(1)
    chat_data = resp.json()
    chat_id = chat_data["id"]
    network_id = chat_data["network_id"]
    print(f"Chat created. ID: {chat_id}, Network ID: {network_id}")

    # 3. Upload GraphML
    print("Uploading GraphML...")
    files = {"file": ("test.graphml", TEST_GRAPHML, "application/xml")}
    resp = requests.post(f"{BASE_URL}/chat/{chat_id}/upload", headers=headers, files=files)
    if resp.status_code != 202:
        print(f"Upload failed: {resp.text}")
        sys.exit(1)
    print("Upload accepted.")

    # 4. Wait for processing and check attributes
    print("Waiting for processing and checking attributes...")
    max_retries = 10
    for i in range(max_retries):
        time.sleep(2)
        try:
            # Check Node Attributes
            resp = requests.get(f"{NX_API_URL}/tools/list_node_attributes", params={"network_id": network_id})
            if resp.status_code == 200:
                attrs = resp.json()
                print(f"Current node attributes: {attrs}")
                
                expected_node_attrs = ["test_str_attr", "test_int_attr", "test_float_attr"]
                missing_node = [attr for attr in expected_node_attrs if attr not in attrs]
                
                if missing_node:
                     print(f"Missing node attributes: {missing_node}")
                
                # Check Edge Attributes
                resp_edge = requests.get(f"{NX_API_URL}/tools/list_edge_attributes", params={"network_id": network_id})
                if resp_edge.status_code == 200:
                    edge_attrs = resp_edge.json()
                    print(f"Current edge attributes: {edge_attrs}")
                    
                    expected_edge_attrs = ["test_edge_str", "test_edge_float"]
                    missing_edge = [attr for attr in expected_edge_attrs if attr not in edge_attrs]
                    
                    if not missing_node and not missing_edge:
                        print("SUCCESS: All expected node and edge attributes found!")
                        return
                    elif missing_edge:
                        print(f"Missing edge attributes: {missing_edge}")
                else:
                     print(f"Failed to list edge attributes: {resp_edge.status_code} {resp_edge.text}")

            else:
                print(f"Failed to list node attributes: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Error checking attributes: {e}")
            
    print("FAILURE: Timed out waiting for attributes.")
    sys.exit(1)

if __name__ == "__main__":
    run_verification()
