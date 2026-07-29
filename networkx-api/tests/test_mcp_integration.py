import pytest
from unittest.mock import MagicMock, patch
from app.mcp import tools
from app.mcp import resources

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
