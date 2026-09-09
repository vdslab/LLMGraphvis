from unittest.mock import patch

import pytest
from app.logic.extraction import extract_nodes
from test_layout_parameters import setup_graph

from common import models


def test_extraction_creates_fresh_snapshot_without_layout(db):
    setup_graph(db)
    with patch("app.logic.subgraph.calculate_layout") as layout:
        first = extract_nodes(1, ["n0", "n1"], db)
        second = extract_nodes(1, ["n0", "n1", "n2"], db)
    layout.assert_not_called()
    assert "new_network_id" not in first
    assert first["created_network_id"] != second["created_network_id"]
    assert db.query(models.NodeAttribute).count() == 0
    network = db.get(models.Network, first["created_network_id"])
    assert network.parent_network_id == 1
    assert network.last_layout_name is None
    assert db.query(models.Edge).filter_by(network_id=network.id).count() == 1


def test_unknown_nodes_are_rejected_before_creating_network(db):
    setup_graph(db)
    with pytest.raises(ValueError, match="Unknown node"):
        extract_nodes(1, ["n0", "typo"], db)
    assert db.query(models.Network).count() == 1
