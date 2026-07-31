from unittest.mock import MagicMock, patch

import pytest
from app.core.mcp import mcp
from app.mcp import resources, tools

from common import models


@pytest.fixture
def mock_importer():
    # Correct function name: parse_and_save_graphml
    with patch("app.logic.importer.parse_and_save_graphml") as mock:
        yield mock

@pytest.fixture
def mock_layout():
    with patch("app.logic.layout.calculate_layout") as mock:
        yield mock

@pytest.fixture
def mock_builder():
    with patch("app.logic.visualization_builder.build_visualization") as mock:
        mock.return_value = {"nodes": [{"id": "n1"}], "edges": []}
        yield mock

def test_initialize_network_structure(mock_importer, mock_layout, mock_builder):
    """
    Test that the network_initialize tool calls all logic components correctly.
    """
    mock_importer.return_value = 101 # Final network ID

    with patch("app.core.database.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        # Execute
        result = tools.network_initialize(100, "<xml></xml>")

        # Verify
        mock_importer.assert_called_with(100, "<xml></xml>", mock_db)
        mock_layout.assert_called_with(101, "forceatlas2", mock_db)
        mock_builder.assert_called_with(mock_db, 101)

        assert result["network_id"] == 101
        assert len(result["network"]["nodes"]) == 1

        mock_db.close.assert_called()

def test_resources_execution():
    """
    Test that resources open/close DB and call logic.
    """
    with patch("app.core.database.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        # Correct function name: get_network_metadata
        with patch("app.logic.network_metadata.get_network_metadata") as mock_meta:
            mock_meta.return_value = {"name": "Test"}

            res = resources.get_network_metadata(1)

            assert res == {"name": "Test"}
            mock_meta.assert_called_with(mock_db, 1)
            mock_db.close.assert_called()


def test_resources_return_data_not_errors(db):
    """Every resource must reach a logic function that still exists.

    Resources swallow exceptions into {"error": ...}, so a renamed logic helper
    fails silently — which is how the attribute resources shipped broken and the
    backend reported "no attributes" for every network.
    """
    net = models.Network(name="ResourceNet", description="desc")
    db.add(net)
    db.commit()

    n1 = models.Node(network_id=net.id, node_id="n1", label="N1")
    n2 = models.Node(network_id=net.id, node_id="n2", label="N2")
    db.add_all([n1, n2])
    db.commit()
    db.add(
        models.Edge(
            network_id=net.id,
            edge_id="e1",
            source_node_id=n1.id,
            target_node_id=n2.id,
        )
    )
    db.commit()

    session_proxy = MagicMock(wraps=db)
    session_proxy.close.return_value = None

    with patch("app.core.database.SessionLocal", return_value=session_proxy):
        assert resources.get_network_metadata(net.id)["name"] == "ResourceNet"

        structure = resources.get_structure_resource(net.id)
        assert structure["node_count"] == 2
        assert structure["edge_count"] == 1

        # A list (the core attributes are always present), never an error dict.
        node_attrs = resources.get_node_attributes_resource(net.id)
        edge_attrs = resources.get_edge_attributes_resource(net.id)
        assert isinstance(node_attrs, list)
        assert isinstance(edge_attrs, list)
        assert "label" in {a["name"] for a in node_attrs}
        assert resources.get_subgraphs_resource(net.id) == []


def test_resources_declare_json_mime_type():
    """The backend parses resource bodies as JSON; FastMCP defaults templates to
    text/plain unless mime_type is passed explicitly."""
    templates = mcp._resource_manager._templates.values()
    network_templates = [
        t for t in templates if str(t.uri_template).startswith("network://")
    ]

    assert network_templates, "no network:// resource templates registered"
    for template in network_templates:
        assert template.mime_type == "application/json", (
            f"{template.uri_template} declares {template.mime_type}"
        )
