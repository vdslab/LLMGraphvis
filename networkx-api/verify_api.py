
import requests
import json
import networkx as nx

BASE_URL = "http://localhost:8000/api/v1/networks"


def test_api():
    print("Testing API Endpoints...")
    
    # 1. Initialize Network
    print("\n1. Testing /initialize")
    G = nx.karate_club_graph()
    graphml_data = "".join(nx.generate_graphml(G))
    
    response = requests.post(
        f"{BASE_URL}/initialize",
        json={"network_id": 999, "graphml_data": graphml_data}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    network_id = response.json()["network_id"]
    
    # 2. Attributes
    print("\n2. Testing /attributes/nodes")
    response = requests.get(f"{BASE_URL}/{network_id}/attributes/nodes")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()[:2]}") # Show first 2
    assert response.status_code == 200

    # 3. Layout
    print("\n3. Testing /layout")
    response = requests.post(
        f"{BASE_URL}/{network_id}/layout",
        json={"layout_name": "circular"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200

    # 4. Centrality
    print("\n4. Testing /analysis/centrality")
    response = requests.post(
        f"{BASE_URL}/{network_id}/centrality",
        json={"centrality_type": "degree"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200

    # 5. Top Nodes
    print("\n5. Testing /nodes/top")
    response = requests.get(
        f"{BASE_URL}/{network_id}/nodes/top?metric=degree&k=3"
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200

    # 6. Visualization
    print("\n6. Testing /visualization")
    response = requests.post(
        f"{BASE_URL}/{network_id}/visualization",
        json={"layout_name": "circular"}
    )
    print(f"Status: {response.status_code}")
    # Don't print full vis data, it's large
    print(f"Response keys: {response.json().keys()}") 
    assert response.status_code == 200

    # 7. Subgraph (Largest Component)
    print("\n7. Testing /subgraphs/largest-component")
    response = requests.post(
        f"{BASE_URL}/{network_id}/subgraphs/largest-component"
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200

    print("\nVerification Complete!")

if __name__ == "__main__":
    try:
        test_api()
    except Exception as e:
        print(f"\nVerification Failed: {e}")
