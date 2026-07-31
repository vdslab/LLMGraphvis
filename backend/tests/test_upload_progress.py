"""The upload pipeline reports steps, not thoughts.

No model runs during an upload, so labelling "Importing GraphML data…" as the
agent's reasoning — which is what `thinking_stream` renders as in the UI — told
the user something untrue. These tests pin the split: fixed steps go out as
`progress` events and are persisted in a `<steps>` block, and `<thought>` is
left to the engine.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services import chat_service

from common import models


def _events(mock_queue):
    return [call[0][0] for call in mock_queue.put.call_args_list]


async def _run_upload(overview=("", ""), *, name_is_custom=True, network_name="New Chat Network"):
    with patch(
        "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
    ) as mock_exec, patch(
        "app.services.llm.get_event_queue", new_callable=AsyncMock
    ) as mock_get_queue, patch(
        "app.services.llm.context.build_data_overview", new_callable=AsyncMock
    ) as mock_overview, patch(
        "app.core.database.SessionLocal"
    ) as mock_session_cls:
        mock_exec.return_value = {"network_id": 100, "nodes": [], "links": []}
        mock_overview.return_value = overview
        mock_queue = AsyncMock()
        mock_get_queue.return_value = mock_queue

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_chat = MagicMock()
        mock_chat.id = 1
        mock_chat.network_id = 100
        mock_chat.name = "My analysis"
        mock_chat.name_is_custom = name_is_custom
        mock_network = MagicMock()
        mock_network.name = network_name

        def route_query(model):
            query = MagicMock()
            query.filter.return_value.first.return_value = (
                mock_network if model is models.Network else mock_chat
            )
            return query

        mock_db.query.side_effect = route_query

        await chat_service.handle_upload_background(
            1, 100, "<graphml></graphml>", "karate_club.graphml"
        )

        saved = mock_db.add.call_args[0][0]
        return _events(mock_queue), saved.content, mock_network


@pytest.mark.asyncio
async def test_pipeline_steps_are_progress_events_not_thinking():
    events, _, _ = await _run_upload()

    assert not [e for e in events if e["event"] == "thinking_stream"]
    labels = [
        json.loads(e["data"])["label"] for e in events if e["event"] == "progress"
    ]
    assert "Importing GraphML data" in labels
    assert "Calculating ForceAtlas2 layout" in labels
    assert "Generating initial visualization" in labels


@pytest.mark.asyncio
async def test_last_step_is_reported_finished():
    """Without a closing 'done', the UI would show the final step spinning
    forever whenever the turn produces no further events."""
    events, _, _ = await _run_upload()

    progress = [json.loads(e["data"]) for e in events if e["event"] == "progress"]
    assert progress[-1]["status"] == "done"


@pytest.mark.asyncio
async def test_saved_message_records_steps_without_claiming_they_were_thought():
    _, content, _ = await _run_upload()

    assert "<steps>" in content
    assert "Importing GraphML data" in content
    assert "<thought>" not in content


@pytest.mark.asyncio
async def test_overview_is_saved_folded_behind_its_title():
    _, content, _ = await _run_upload(
        overview=("Uploaded network — Karate — 34 nodes, 78 edges", "- **Size:** …")
    )

    assert '<collapsible title="Uploaded network — Karate — 34 nodes, 78 edges">' in content
    assert "- **Size:** …" in content


@pytest.mark.asyncio
async def test_message_omits_the_collapsible_when_there_is_no_overview():
    _, content, _ = await _run_upload(overview=("", ""))

    assert "<collapsible" not in content
    assert "Graph uploaded and initialized successfully." in content


@pytest.mark.asyncio
async def test_upload_names_the_network_after_the_file():
    """A network is created as "<chat name> Network" before anything is in it,
    so leaving that name in place reports "New Chat Network" to the user and to
    the agent as if it were the graph's own."""
    _, _, network = await _run_upload()

    assert network.name == "karate club"


@pytest.mark.asyncio
async def test_upload_leaves_a_real_network_name_alone():
    _, _, network = await _run_upload(network_name="Concert co-performance")

    assert network.name == "Concert co-performance"
