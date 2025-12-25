
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import json
from google.genai import types
from app.services.llm.engine import execute_tool_loop, _consume_stream, _handle_tool_execution, _handle_visualization_update

@pytest.mark.asyncio
async def test_consume_stream_text_only():
    # Mock response object
    mock_chunk = MagicMock()
    mock_chunk.candidates = [MagicMock()]
    mock_chunk.candidates[0].content.parts = [MagicMock(text="Hello", function_call=None)]
    
    # Create an async iterator for the response
    async def response_stream():
        yield mock_chunk

    mock_queue = AsyncMock()
    
    text, function_calls = await _consume_stream(response_stream(), mock_queue)
    
    assert text == "Hello"
    assert len(function_calls) == 0
    mock_queue.put.assert_called() # Should emit message_chunk

@pytest.mark.asyncio
async def test_consume_stream_function_calls():
    # Mock response object with function call
    mock_chunk = MagicMock()
    mock_chunk.candidates = [MagicMock()]
    fc = MagicMock()
    # Need to set name explicitly on the mock instance, otherwise it's just a child mock "name"
    fc.configure_mock(name="get_node") 
    fc.args = {"id": 1}
    
    # Parts can contain function call
    mock_chunk.candidates[0].content.parts = [MagicMock(text=None, function_call=fc)]
    
    async def response_stream():
        yield mock_chunk

    mock_queue = AsyncMock()
    
    text, function_calls = await _consume_stream(response_stream(), mock_queue)
    
    assert text == ""
    assert len(function_calls) == 1
    assert function_calls[0].name == "get_node"

@pytest.mark.asyncio
async def test_consume_stream_multiple_function_calls():
    # Mock response with multiple chunks/function calls
    mock_chunk1 = MagicMock()
    fc1 = MagicMock()
    fc1.configure_mock(name="tool1")
    fc1.args = {"x": 1}
    mock_chunk1.candidates = [MagicMock()]
    mock_chunk1.candidates[0].content.parts = [MagicMock(text=None, function_call=fc1)]
    
    mock_chunk2 = MagicMock()
    fc2 = MagicMock()
    fc2.configure_mock(name="tool2")
    fc2.args = {"y": 2}
    mock_chunk2.candidates = [MagicMock()]
    mock_chunk2.candidates[0].content.parts = [MagicMock(text=None, function_call=fc2)]
    
    async def response_stream():
        yield mock_chunk1
        yield mock_chunk2

    mock_queue = AsyncMock()
    
    text, function_calls = await _consume_stream(response_stream(), mock_queue)
    
    assert len(function_calls) == 2
    assert function_calls[0].name == "tool1"
    assert function_calls[1].name == "tool2"

@patch("app.services.llm.engine.mcp_client")
@patch("app.services.llm.engine.local_tools")
@pytest.mark.asyncio
async def test_handle_tool_execution_local(mock_local, mock_mcp):
    mock_local.execute_local_tool = AsyncMock(return_value="local_result")
    
    result, status, error = await _handle_tool_execution(
        "switch_to_main_network", {}, 1, 100, MagicMock()
    )
    
    assert result == "local_result"
    assert status == "completed"
    assert error is None
    mock_local.execute_local_tool.assert_called_once()
    mock_mcp.execute_tool.assert_not_called()

@patch("app.services.llm.engine.mcp_client")
@pytest.mark.asyncio
async def test_handle_tool_execution_mcp(mock_mcp):
    mock_mcp.execute_tool = AsyncMock(return_value="mcp_result")
    
    result, status, error = await _handle_tool_execution(
        "some_mcp_tool", {"arg": 1}, 1, 100, MagicMock()
    )
    
    assert result == "mcp_result"
    assert status == "completed"
    assert error is None
    mock_mcp.execute_tool.assert_called_once()

@pytest.mark.asyncio
async def test_handle_visualization_update_context_switch(db): # Needs DB fixture
    # We need a chat in DB
    from common import models
    chat = models.Chat(id=999, user_id=1, network_id=10, name="Test")
    db.add(chat)
    db.commit()

    mock_queue = AsyncMock()
    
    with patch("app.services.llm.engine.mcp_client") as mock_mcp:
        mock_mcp.execute_tool = AsyncMock(return_value={"nodes": [], "links": []}) # For auto-gen
        
        new_network_id = 20
        tool_result = {"new_network_id": new_network_id}
        
        result_id = await _handle_visualization_update(
            "switch_to_main_network", tool_result, 10, 999, db, mock_queue
        )
        
        assert result_id == new_network_id
        
        # Verify DB update
        db.refresh(chat)
        assert chat.network_id == new_network_id
        
        # Verify render update emitted
        assert mock_queue.put.call_count >= 1

@patch("app.services.llm.engine.client")
@patch("app.services.llm.engine.mcp_client")
@patch("app.services.llm.engine.local_tools")
@patch("app.services.llm.engine._consume_stream")
@pytest.mark.asyncio
async def test_execute_tool_loop_single_iteration(
    mock_consume, mock_local, mock_mcp, mock_client
):
    # Setup mocks
    # First iteration: returns text, no function calls
    mock_consume.return_value = ("Response Text", [])
    
    history = []
    queue = AsyncMock()
    
    result = await execute_tool_loop(
        MagicMock(), 1, history, queue, {}, 1, MagicMock()
    )
    
    assert result == "Response Text"
    # Should not call generate_content again because no tool calls
    mock_client.aio.models.generate_content_stream.assert_not_called()

