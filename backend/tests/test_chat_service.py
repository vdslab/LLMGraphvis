import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from common import models
from app.services import chat_service
from app.services.llm.providers.types import UsageData

@pytest.mark.asyncio
async def test_handle_process_background_success(db):
    """
    Test that process_background calls LLM service and saves messages.
    """
    # Setup
    chat_id = 1
    user_message = "Hello AI"
    fake_response = "Hello Human"

    # Mock LLM Service — process_chat returns
    # (final_text, execution_log, total_usage, provider_name, model_name)
    with patch("app.services.llm.process_chat", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = (
            fake_response,
            [],
            UsageData(),
            "google",
            "gemini-2.5-flash",
        )

        # Mock Queue
        mock_queue = AsyncMock()
        with patch("app.services.llm.get_event_queue", new_callable=AsyncMock) as mock_get_queue:
            mock_get_queue.return_value = mock_queue

            # Mock DB Session used inside service (it creates its own SessionLocal)
            # We need to intercept SessionLocal to return our test 'db' or a mock
            # BE CAREFUL: Service uses `database.SessionLocal()`.
            # Ideally we patch `app.core.database.SessionLocal` to return a mock that commits.

            with patch("app.core.database.SessionLocal") as mock_session_cls:
                mock_db_instance = MagicMock()
                mock_session_cls.return_value = mock_db_instance

                # Execute
                await chat_service.handle_process_background(chat_id, user_message)

                # Verify
                mock_process.assert_called_once()
                # Check that a message was added (mock_db_instance.add called)
                assert mock_db_instance.add.call_count >= 1
                mock_db_instance.commit.assert_called()

                # Verify Event emitted
                mock_get_queue.assert_called_with(chat_id)
                assert mock_queue.put.call_count >= 1
                args, _ = mock_queue.put.call_args
                event_data = args[0]
                assert event_data["event"] == "message_complete"

@pytest.mark.asyncio
async def test_handle_upload_background_success(db):
    """
    Test that upload_background runs the import -> layout -> visualization
    pipeline via the MCP client and updates the chat.
    """
    chat_id = 1
    initial_network_id = 100
    new_network_id = 101
    graphml = "<graph></graph>"

    # Mock MCP Client — the same dict works for all three pipeline steps:
    # import reads "network_id", layout ignores dicts, visualization has no "error".
    with patch("app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {
            "network_id": new_network_id,
            "nodes": [],
            "links": [],
        }

        # Mock Queue
        mock_queue = AsyncMock()
        with patch("app.services.llm.get_event_queue", new_callable=AsyncMock) as mock_get_queue:
            mock_get_queue.return_value = mock_queue

            # Mock DB for Chat update
            with patch("app.core.database.SessionLocal") as mock_session_cls:
                mock_db = MagicMock()
                mock_session_cls.return_value = mock_db

                # Setup mock chat query result
                mock_chat = MagicMock()
                mock_chat.id = chat_id
                mock_chat.network_id = initial_network_id

                mock_query = mock_db.query.return_value
                mock_filter = mock_query.filter.return_value
                mock_filter.first.return_value = mock_chat

                # Execute
                await chat_service.handle_upload_background(chat_id, initial_network_id, graphml)

                # Verify the three pipeline steps were called
                mock_exec.assert_any_call(
                    "network_import_graphml",
                    {"network_id": initial_network_id, "graphml_data": graphml},
                )
                mock_exec.assert_any_call(
                    "layout_forceatlas2", {"network_id": new_network_id}
                )
                mock_exec.assert_any_call(
                    "visualization_generate", {"network_id": new_network_id}
                )

                # Verify Chat updated
                assert mock_chat.network_id == new_network_id
                mock_db.commit.assert_called()

                # Verify 'render_update' event
                found_render = False
                for call in mock_queue.put.call_args_list:
                    if call[0][0]["event"] == "render_update":
                        found_render = True
                assert found_render
