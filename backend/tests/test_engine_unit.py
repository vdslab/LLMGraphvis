import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm.engine import GraphVisAgent, _truncate_tool_result
from app.services.llm.providers.google_genai import (
    GoogleGenAIProvider,
    _is_retryable_error,
)
from app.services.llm.providers.types import (
    FunctionCallData,
    StreamChunk,
    UsageData,
)


@pytest.fixture
def mock_agent():
    # Patch the provider factory so no real LLM client is created
    with patch("app.services.llm.engine._create_provider") as mock_factory:
        mock_provider = MagicMock()
        mock_provider.model_name = "test-model"
        mock_factory.return_value = mock_provider
        agent = GraphVisAgent(db=None)
    return agent


@pytest.fixture
def mock_queue():
    return AsyncMock()


async def _async_iter(items):
    for item in items:
        yield item


# --- _consume_stream ---

@pytest.mark.asyncio
async def test_consume_stream_text_only(mock_agent, mock_queue):
    """Test consuming a stream that only contains text."""
    stream = _async_iter([StreamChunk(text="Hello"), StreamChunk(text=" World")])

    text, thought, tool_calls, usage = await mock_agent._consume_stream(stream, mock_queue)

    assert text == "Hello World"
    assert thought == ""
    assert tool_calls == []
    # One message_chunk event per text chunk
    assert mock_queue.put.call_count == 2


@pytest.mark.asyncio
async def test_consume_stream_with_tool_call(mock_agent, mock_queue):
    """Test consuming a stream that has a tool call."""
    fc = FunctionCallData(name="get_network_structure", args={})
    stream = _async_iter([
        StreamChunk(text="I will check."),
        StreamChunk(function_calls=[fc]),
    ])

    text, thought, tool_calls, usage = await mock_agent._consume_stream(stream, mock_queue)

    assert text == "I will check."
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "get_network_structure"


@pytest.mark.asyncio
async def test_consume_stream_accumulates_usage(mock_agent, mock_queue):
    """Usage chunks are summed defensively even if yielded more than once."""
    stream = _async_iter([
        StreamChunk(text="hi", usage=UsageData(input_tokens=10, output_tokens=5)),
        StreamChunk(usage=UsageData(input_tokens=1, output_tokens=2, cached_input_tokens=3)),
    ])

    _, _, _, usage = await mock_agent._consume_stream(stream, mock_queue)

    assert usage.input_tokens == 11
    assert usage.output_tokens == 7
    assert usage.cached_input_tokens == 3


# --- lazy intent detection ---

@pytest.mark.asyncio
async def test_check_and_handle_lazy_intent_detected(mock_agent, mock_queue):
    """Lazy intent ("I will ...") appends a nudge to history and returns True."""
    history = []
    text_content = "I will visualize the network now."

    result = await mock_agent._check_and_handle_lazy_intent(
        text_content, history, {}, mock_queue, [], None
    )

    assert result is True
    assert len(history) == 2
    assert history[0].role == "model"
    assert history[0].parts[0].text == text_content
    assert history[1].role == "user"
    assert "proceed" in history[1].parts[0].text.lower()


@pytest.mark.asyncio
async def test_check_and_handle_lazy_intent_not_lazy(mock_agent, mock_queue):
    """A normal final answer is not treated as lazy intent."""
    history = []

    result = await mock_agent._check_and_handle_lazy_intent(
        "Here is the result.", history, {}, mock_queue, [], None
    )

    assert result is False
    assert len(history) == 0


# --- tool execution ---

@pytest.mark.asyncio
async def test_execute_tools_and_update_history(mock_agent, mock_queue):
    """Tool execution appends model + tool turns and records the step log."""
    mock_agent._run_tool = AsyncMock(return_value=({"nodes": []}, "completed", None))
    mock_agent._handle_side_effects = AsyncMock()

    fc = FunctionCallData(name="test_tool", args={"param": 1}, call_id="call_1")
    history = []
    loop_context = {"network_id": 1}

    step_log = await mock_agent._execute_tools_and_update_history(
        [fc], "Calling tool.", "", history, mock_queue,
        chat_id=1, loop_context=loop_context, session=None,
    )

    mock_agent._run_tool.assert_called_once()
    assert mock_agent._run_tool.call_args[0][0] == "test_tool"

    assert len(history) == 2
    assert history[0].role == "model"
    assert history[1].role == "tool"

    assert loop_context["tools_executed"] is True
    assert step_log["tool_calls"][0]["name"] == "test_tool"
    assert step_log["tool_calls"][0]["status"] == "completed"


# --- result truncation ---

def test_truncate_tool_result_limits_long_lists():
    result = {"items": list(range(100)), "nested": [list(range(20))]}
    truncated = _truncate_tool_result(result, max_list_items=15)

    assert len(truncated["items"]) == 16  # 15 items + omission marker
    assert "omitted" in truncated["items"][-1]
    assert len(truncated["nested"][0]) == 16


# --- retry predicate & retry behavior (Google provider) ---

def test_is_retryable_error():
    """Test the retry predicate."""
    class MockError:
        def __init__(self, code=None, status=None, message=""):
            self.code = code
            self.status = status
            self.message = message

        def __str__(self):
            return self.message

    # True cases
    assert _is_retryable_error(MockError(code=429))
    assert _is_retryable_error(MockError(code=503))
    assert _is_retryable_error(MockError(status="RESOURCE_EXHAUSTED"))
    assert _is_retryable_error(MockError(message="Service Unavailable"))

    # False cases
    assert not _is_retryable_error(MockError(code=400))
    assert not _is_retryable_error(MockError(code=404))
    assert not _is_retryable_error(MockError(message="Syntax Error"))


@pytest.fixture
def mock_google_provider():
    with patch.object(GoogleGenAIProvider, "_initialize_client", return_value=MagicMock()):
        provider = GoogleGenAIProvider()
    return provider


@pytest.mark.asyncio
async def test_raw_generate_retry_success(mock_google_provider):
    """Retries on 429 and eventually succeeds."""
    class MockError(Exception):
        def __init__(self, code=None):
            self.code = code

    mock_google_provider.client.aio.models.generate_content_stream = AsyncMock(
        side_effect=[MockError(code=429), "Success"]
    )

    # Patch asyncio.sleep so tenacity's exponential backoff doesn't slow the test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await mock_google_provider._raw_generate([], [], None)

    assert result == "Success"
    assert mock_google_provider.client.aio.models.generate_content_stream.call_count == 2


@pytest.mark.asyncio
async def test_raw_generate_fail_non_retryable(mock_google_provider):
    """Does NOT retry on a non-retryable error."""
    class MockError(Exception):
        def __init__(self, code=None):
            self.code = code

    mock_google_provider.client.aio.models.generate_content_stream = AsyncMock(
        side_effect=[MockError(code=400), "Success"]
    )

    with pytest.raises(MockError):
        await mock_google_provider._raw_generate([], [], None)

    assert mock_google_provider.client.aio.models.generate_content_stream.call_count == 1
