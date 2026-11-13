import json
from unittest.mock import AsyncMock

import pytest

from evaluation.tests.test_friction_journal import _bridge


@pytest.mark.asyncio
async def test_target_feedback_is_separate_and_requires_reset(tmp_path):
    bridge = _bridge(tmp_path)
    session = bridge.sessions["session-1"]
    bridge.api.send_message = AsyncMock(
        return_value={
            "assistant_message": "The size argument needs a clearer area description.",
            "provider": "lmstudio",
            "model": "test-model",
            "tools_called": [],
            "tool_executions": [],
            "visualization_state": {"render": {}},
            "visualization_diff": {"changed": False},
        }
    )
    note = await bridge.ask_target_feedback("session-1", 1)
    assert note["status"] == "unverified_target_feedback"
    assert note["model"] == "test-model"
    assert session.probe_count == 1
    assert len(session.observations) == 1
    assert not session.friction_notes
    stored = json.loads((bridge.config.run_dir / "sessions/session-1.json").read_text())
    assert stored["target_feedback"] == [note]
    with pytest.raises(ValueError, match="already"):
        await bridge.ask_target_feedback("session-1", 1)
    with pytest.raises(ValueError, match="Reset"):
        await bridge.send("session-1", "Another probe", False)
    await bridge.api.close()


@pytest.mark.asyncio
async def test_feedback_requires_observed_probe_and_records_unintended_actions(
    tmp_path,
):
    bridge = _bridge(tmp_path)
    bridge.api.send_message = AsyncMock(
        return_value={
            "assistant_message": "I changed the picture.",
            "provider": "lmstudio",
            "model": "test-model",
            "tools_called": ["visualization_generate"],
            "tool_executions": [{"tool_name": "visualization_generate"}],
            "visualization_state": {"render": {}},
            "visualization_diff": {"changed": True},
        }
    )
    with pytest.raises(ValueError, match="latest"):
        await bridge.ask_target_feedback("session-1", 2)
    bridge.api.send_message.assert_not_called()
    note = await bridge.ask_target_feedback("session-1", 1)
    assert note["tools_called"] == ["visualization_generate"]
    assert note["visualization_diff"]["changed"] is True
    await bridge.api.close()


@pytest.mark.asyncio
async def test_old_probe_cannot_be_used_after_reset(tmp_path):
    bridge = _bridge(tmp_path)
    bridge.sessions["session-1"].chat_id = 2
    bridge.api.send_message = AsyncMock()
    with pytest.raises(ValueError, match="latest"):
        await bridge.ask_target_feedback("session-1", 1)
    bridge.api.send_message.assert_not_called()
    await bridge.api.close()
