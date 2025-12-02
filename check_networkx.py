import requests
import sys

def check_networkx():
    url = "http://localhost:8001/health" # Assuming health endpoint exists, or just root
    try:
        print(f"Checking {url}...")
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # Also check a tool endpoint
    url_tool = "http://localhost:8001/tools/list_node_attributes?network_id=1"
    try:
        print(f"Checking {url_tool}...")
        response = requests.get(url_tool, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_networkx()
