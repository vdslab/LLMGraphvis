from app import models
from app.logic import network_service


def test_get_network_metadata(db):
    # Setup
    network = models.Network(name="TestNet", description="A test network")
    db.add(network)
    db.commit()

    # Execute
    metadata = network_service.get_network_metadata(db, network.id)

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
    msg = network_service.update_network_metadata(
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
    structure = network_service.get_network_structure(db, network.id)

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
    subgraphs = network_service.get_subgraphs(db, parent.id)

    # Verify
    assert len(subgraphs) == 1
    assert subgraphs[0]["name"] == "Child"
