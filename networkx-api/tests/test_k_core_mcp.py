import pytest
from unittest.mock import MagicMock, patch
from app.mcp.tools import subgraph


def test_create_k_core_subgraph_success():
    """
    Test that the subgraph_k_core tool calls logic correctly.
    """
    # get_db_context() calls SessionLocal() at runtime, so patching SessionLocal
    # works even though the tool module imported get_db_context directly.
    with patch("app.core.database.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        with patch("app.logic.subgraph.create_k_core_subgraph") as mock_logic_create:
            with patch("app.logic.visualization_builder.build_visualization") as mock_build_vis:

                # Setup return values
                mock_logic_create.return_value = {"new_network_id": 999, "name": "K-Core (k=2)"}
                mock_build_vis.return_value = {"nodes": [], "edges": []}

                # Execute
                result = subgraph.subgraph_k_core(
                    network_id=10,
                    k=2,
                    preserve_layout=True,
                )

                # Verify Logic Call
                mock_logic_create.assert_called_once_with(
                    source_network_id=10,
                    k=2,
                    db=mock_db,
                    preserve_layout=True,
                )

                # Verify Vis Builder Call
                mock_build_vis.assert_called_once_with(mock_db, 999)

                # Verify Result Structure
                assert result["network_id"] == 999
                assert result["network"] == {"nodes": [], "edges": []}
                assert "content" in result
                assert "K-core subgraph created" in result["content"]


def test_create_k_core_subgraph_error():
    """
    Test error handling when logic raises (e.g. empty k-core).
    handle_tool_errors wraps any exception in a RuntimeError with the
    original message preserved.
    """
    # get_db_context() calls SessionLocal() at runtime, so patching SessionLocal
    # works even though the tool module imported get_db_context directly.
    with patch("app.core.database.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        with patch("app.logic.subgraph.create_k_core_subgraph") as mock_logic_create:
            mock_logic_create.side_effect = ValueError("No k-core found for k=10")

            with pytest.raises(RuntimeError) as excinfo:
                subgraph.subgraph_k_core(network_id=10, k=10)

            assert "No k-core found" in str(excinfo.value)
