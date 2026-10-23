from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        with patch(
            "app.services.llm.get_event_queue", new_callable=AsyncMock
        ) as mock_get_queue:
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
    The upload runs import -> layout -> visualization over networkx-api's REST
    routes, never as MCP tools (ADR 0035), and updates the chat.
    """
    chat_id = 1
    initial_network_id = 100
    new_network_id = 101
    graphml = "<graph></graph>"

    with (
        patch(
            "app.services.network_service.import_graphml", new_callable=AsyncMock
        ) as mock_import,
        patch(
            "app.services.network_service.calculate_layout", new_callable=AsyncMock
        ) as mock_layout,
        patch(
            "app.services.network_service.build_visualization", new_callable=AsyncMock
        ) as mock_vis,
        patch(
            "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
        ) as mock_exec,
        patch(
            "app.services.llm.context.build_data_overview", new_callable=AsyncMock
        ) as mock_overview,
        patch(
            "app.services.llm.get_event_queue", new_callable=AsyncMock
        ) as mock_get_queue,
        patch("app.core.database.SessionLocal") as mock_session_cls,
    ):
        mock_import.return_value = new_network_id
        mock_vis.return_value = {"network_id": new_network_id, "nodes": [], "links": []}
        mock_overview.return_value = ("", "")
        mock_queue = AsyncMock()
        mock_get_queue.return_value = mock_queue

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_chat = MagicMock()
        mock_chat.id = chat_id
        mock_chat.network_id = initial_network_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_chat

        await chat_service.handle_upload_background(
            chat_id, initial_network_id, graphml
        )

        mock_import.assert_awaited_once_with(initial_network_id, graphml)
        mock_layout.assert_awaited_once_with(new_network_id, "forceatlas2")
        mock_vis.assert_awaited_once_with(new_network_id)
        mock_exec.assert_not_called()

        assert mock_chat.network_id == new_network_id
        mock_db.commit.assert_called()
        events = [call[0][0]["event"] for call in mock_queue.put.call_args_list]
        assert "render_update" in events


@pytest.mark.asyncio
async def test_process_chat_failure_emits_agent_error(db):
    """A backend failure must not be sent as an SSE event named `error`:
    EventSource routes that name to onerror, which shows a lost connection."""
    import asyncio
    import json

    from app.services.llm import service

    queue = asyncio.Queue()
    with patch.object(service.events, "get_event_queue", AsyncMock(return_value=queue)):
        text, *_ = await service.process_chat(999999, "hi", db)

    event = queue.get_nowait()
    assert event["event"] == "agent_error"
    assert "Chat not found" in json.loads(event["data"])
    assert text.startswith("I encountered an error")
