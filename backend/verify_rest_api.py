import requests
import json
import sys

BASE_URL = "http://networkx-api:8001/api/v1/networks"
NETWORK_ID = 2  # Assuming network 2 exists from previous tests

def test_metadata_api():
    print(f"Testing Metadata API for Network {NETWORK_ID}...")
    
    # 1. Update Metadata
    url = f"{BASE_URL}/{NETWORK_ID}/metadata"
    payload = {
        "description": "Updated via REST API Verification Script"
    }
    
    print(f"PUT {url} with {payload}")
    response = requests.put(url, json=payload)
    
    if response.status_code != 200:
        print(f"FAILED: PUT returned {response.status_code} - {response.text}")
        sys.exit(1)
        
    data = response.json()
    print(f"PUT Response: {json.dumps(data, indent=2)}")
    
    if data["description"] != payload["description"]:
        print("FAILED: Description not updated in response.")
        sys.exit(1)

    # 2. Get Metadata to confirm persistence
    print(f"GET {url}")
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"FAILED: GET returned {response.status_code} - {response.text}")
        sys.exit(1)
        
    data = response.json()
    print(f"GET Response: {json.dumps(data, indent=2)}")
    
    if data["description"] != payload["description"]:
        print("FAILED: Description persistence check failed.")
        sys.exit(1)
        
    print("SUCCESS: REST API Metadata endpoints verified.")

if __name__ == "__main__":
    try:
        test_metadata_api()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
