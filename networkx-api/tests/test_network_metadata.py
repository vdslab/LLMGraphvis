from common import models
from app.logic import network_metadata


def test_get_network_metadata(db):
    # Setup
    network = models.Network(name="TestNet", description="A test network")
    db.add(network)
    db.commit()

    # Execute
    metadata = network_metadata.get_network_metadata(db, network.id)

    # Verify
    assert metadata["id"] == network.id
    assert metadata["name"] == "TestNet"
    assert metadata["description"] == "A test network"
    assert "visual_state" in metadata


def test_update_network_metadata(db):
    # Setup
    network = models.Network(name="OldName", description="OldDesc")
    db.add(network)
    db.commit()

    # Execute
    msg = network_metadata.update_network_metadata(
        db, network.id, name="NewName", description="NewDesc"
    )

    # Verify
    db.refresh(network)
    assert network.name == "NewName"
    assert network.description == "NewDesc"
    assert "updated" in msg


def test_get_network_structure(db):
    # Setup
    network = models.Network(name="StructNet")
    db.add(network)
    db.commit()

    n1 = models.Node(network_id=network.id, node_id="n1", label="N1")
    n2 = models.Node(network_id=network.id, node_id="n2", label="N2")
    db.add(n1)
    db.add(n2)
    db.commit()

    e1 = models.Edge(
        network_id=network.id, edge_id="e1", source_node_id=n1.id, target_node_id=n2.id
    )
    db.add(e1)
    db.commit()

    # Execute
    structure = network_metadata.get_network_structure(db, network.id)

    # Verify
    assert structure["node_count"] == 2
    assert structure["edge_count"] == 1
    # Density: 2 nodes => 1 possible edge. 1 actual edge. Density = 1.0
    assert structure["density"] == 1.0


def test_get_subgraphs(db):
    # Setup
    parent = models.Network(name="Parent")
    db.add(parent)
    db.commit()

    child = models.Network(name="Child", parent_network_id=parent.id)
    db.add(child)
    db.commit()

    # Execute
    subgraphs = network_metadata.get_subgraphs(db, parent.id)

    # Verify
    assert subgraphs[0]["name"] == "Child"


def test_get_visualization_state(db):
    # Setup
    network = models.Network(name="VisNet")
    # Simulate a state where a generic "Community" coloring was applied
    # This JSON structure mimics what VisualizationBuilder interacts with
    network.last_node_color_config = {
        "scale_type": "CATEGORICAL",
        "attribute": "community",
        "color_map": {"0": "#1f77b4", "1": "#ff7f0e"},  # Blue and Orange
    }
    network.last_node_size_config = {
        "attribute": "degree", 
        "min": 5, 
        "max": 15
    }
    
    db.add(network)
    db.commit()

    # Execute
    state = network_metadata.get_visualization_state(db, network.id)

    # Verify
    assert state["network_id"] == network.id
    
    # Check Color Config
    node_color = state["node_color"]
    assert node_color["scale_type"] == "CATEGORICAL"
    assert node_color["attribute"] == "community"
    assert node_color["color_map"]["0"] == "#1f77b4"
    assert node_color["color_map"]["1"] == "#ff7f0e"
    
    # Check Size Config
    node_size = state["node_size"]
    assert node_size["attribute"] == "degree"
