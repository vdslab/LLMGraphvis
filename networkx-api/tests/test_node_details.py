

# Assuming network ID 1 exists from previous tests or seed data
# If not, we might need to create one, but let's try with 1 first or use the logic from other tests


def test_get_node_details_success(client):
    # 1. Create a network with sparse attributes
    graphml_data = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
    <key id="d0" for="node" attr.name="full_attr" attr.type="string"/>
    <key id="d1" for="node" attr.name="sparse_attr" attr.type="string"/>
    <graph id="G" edgedefault="undirected">
        <node id="n0">
            <data key="d0">present</data>
            <!-- d1 is missing for n0 -->
        </node>
        <node id="n1">
            <data key="d0">present_too</data>
            <data key="d1">exists_here</data>
        </node>
    </graph>
</graphml>"""

    response = client.post(
        "/api/v1/networks/initialize",
        json={"network_id": 998, "graphml_data": graphml_data},
    )
    assert response.status_code == 200
    network_id = response.json()["network_id"]

    # 2. Get details for node n0
    response = client.get(f"/api/v1/networks/{network_id}/nodes/n0")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "n0"
    # Verify 'full_attr' is present and correct
    assert data["attributes"]["full_attr"] == "present"
    # Verify 'sparse_attr' is present (via schema) but None
    assert "sparse_attr" in data["attributes"]
    assert data["attributes"]["sparse_attr"] is None


def test_get_node_details_not_found(client):
    # Use a likely non-existent network ID or node ID
    response = client.get("/api/v1/networks/999/nodes/non_existent_node")
    assert response.status_code == 404
