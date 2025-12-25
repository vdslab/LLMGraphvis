import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from app.services.llm.engine import GraphVisAgent
from google.genai import types

# --- Mocks for Google GenAI Types ---
class MockPart:
    def __init__(self, text=None, function_call=None):
        self.text = text
        self.function_call = function_call

class MockContent:
    def __init__(self, parts):
        self.parts = parts

class MockCandidate:
    def __init__(self, content):
        self.content = content

class MockChunk:
    def __init__(self, candidates):
        self.candidates = candidates

@pytest.fixture
def mock_agent():
    # Mock DB if needed, or pass None
    agent = GraphVisAgent(db=None)
    # Mock the internal client to prevent actual API calls
    agent.client = Mock()
    agent.client.aio = Mock()
    agent.client.aio.models = Mock()
    return agent

@pytest.fixture
def mock_queue():
    queue = AsyncMock()
    return queue

# --- Tests ---

@pytest.mark.asyncio
async def test_consume_stream_text_only(mock_agent, mock_queue):
    """Test consuming a stream that only contains text."""
    # Create a mock stream
    chunk1 = MockChunk([MockCandidate(MockContent([MockPart(text="Hello")]))])
    chunk2 = MockChunk([MockCandidate(MockContent([MockPart(text=" World")]))])
    
    # helper to make an async iterator
    async def async_iter(items):
        for item in items:
            yield item

    stream = async_iter([chunk1, chunk2])

    text, tool_calls = await mock_agent._consume_stream(stream, mock_queue)

    assert text == "Hello World"
    assert tool_calls == []
    # Verify queue puts
    assert mock_queue.put.call_count == 2
    
@pytest.mark.asyncio
async def test_consume_stream_with_tool_call(mock_agent, mock_queue):
    """Test consuming a stream that has a tool call."""
    # Mock FunctionCall object
    fc = MagicMock()
    fc.name = "get_network_structure"
    fc.args = {} 

    chunk1 = MockChunk([MockCandidate(MockContent([MockPart(text="I will check.")]))])
    chunk2 = MockChunk([MockCandidate(MockContent([MockPart(function_call=fc)]))])

    async def async_iter(items):
        for item in items:
            yield item

    stream = async_iter([chunk1, chunk2])

    text, tool_calls = await mock_agent._consume_stream(stream, mock_queue)

    assert text == "I will check."
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "get_network_structure"

@pytest.mark.asyncio
async def test_check_and_handle_lazy_intent_detected(mock_agent, mock_queue):
    """Test that lazy intent is detected and triggers retry logic (returns True)."""
    
    # Mock _is_lazy_response to return True
    mock_agent._is_lazy_response = AsyncMock(return_value=True)
    
    history = []
    text_content = "I will analyze the network now."
    loop_context = {}
    
    result = await mock_agent._check_and_handle_lazy_intent(
        text_content, history, loop_context, mock_queue, [], None
    )
    
    assert result is True
    # Verify history was updated
    assert len(history) == 2
    assert history[0].parts[0].text == text_content
    assert "SYSTEM_ALERT" in history[1].parts[0].text

@pytest.mark.asyncio
async def test_check_and_handle_lazy_intent_not_lazy(mock_agent, mock_queue):
    """Test that non-lazy response returns False."""
    
    mock_agent._is_lazy_response = AsyncMock(return_value=False)
    
    history = []
    text_content = "Here is the result."
    
    result = await mock_agent._check_and_handle_lazy_intent(
        text_content, history, {}, mock_queue, [], None
    )
    
    assert result is False
    assert len(history) == 0

@pytest.mark.asyncio
async def test_execute_tools_and_update_history(mock_agent, mock_queue):
    """Test tool execution logic."""
    
    # Mock _run_tool to return success
    # We must properly mock the result so it can be used in from_function_response
    mock_agent._run_tool = AsyncMock(return_value=({"nodes": []}, "completed", None))
    mock_agent._handle_side_effects = AsyncMock() # visual updates
    
    # Use real types.FunctionCall
    fc = types.FunctionCall(name="test_tool", args={"param": 1})
    
    history = []
    text_content = "Calling tool."
    
    # We need to construct parts manually if we want to bypass pydantic validation of "fc" inside the list?
    # No, types.FunctionCall is valid.
    # However, engine.py does: function_calls_parts.append(fc)
    # But wait, types.Part can hold a function_call. 
    # The actual gathered function calls from the stream are types.FunctionCall objects? or types.Part objects?
    # In _consume_stream, we do: all_function_calls.append(part.function_call) -> This IS a FunctionCall object.
    
    # BUT: history.append(types.Content(..., parts=function_calls_parts))
    # function_calls_parts is a list of... what?
    # It contains "types.Part.from_text" AND "fc".
    # Pydantic Content model expects 'parts' to be a list of Part objects.
    # Does types.Content accept FunctionCall directly in parts list? 
    # Usually you need types.Part(function_call=fc).
    
    # Let's check engine.py again.
    # function_calls_parts.append(fc)
    # So `fc` MUST be a Part, or Content can autoconvert? 
    # Inspecting GenAI SDK: usually we receive FunctionCall objects from part.function_call.
    # To put them back into history, we need types.Part(function_call=fc).
    
    # My code in engine.py:
    # for fc in function_calls:
    #    function_calls_parts.append(fc)
    
    # Is `fc` in `function_calls` a FunctionCall or a Part?
    # In `_consume_stream`: all_function_calls.append(part.function_call) -> It's a FunctionCall.
    # So `function_calls_parts.append(fc)` appends a FunctionCall to a list of parts.
    # types.Content(parts=[FunctionCall]) -> MIGHT be invalid if SDK doesn't coerc.
    
    # I should probably fix engine.py to wrap it: types.Part(function_call=fc)
    # Let's verify this.
    
    await mock_agent._execute_tools_and_update_history(
        [fc], text_content, history, mock_queue, chat_id=1, loop_context={"network_id": 1}
    )
    
    # Check execution
    mock_agent._run_tool.assert_called_once()
    assert mock_agent._run_tool.call_args[0][0] == "test_tool"
    
    # Check history update
    assert len(history) == 2
    assert history[0].role == "model"
    assert history[1].role == "user"
