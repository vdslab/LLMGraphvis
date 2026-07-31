import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm.engine import GraphVisAgent, _truncate_tool_result
from app.services.llm.hooks import new_turn_state
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


# --- stalled intent detection ---
#
# The keyword heuristic that used to live on the agent as
# _check_and_handle_lazy_intent is now the nudge_stalled_intent NO_TOOL_CALLS
# hook. Its own behaviour (including the Japanese patterns the old English-only
# version missed) is covered in tests/test_hooks_guards.py; here we only check
# that the loop honours a continuation request.


@pytest.mark.asyncio
async def test_loop_regenerates_on_a_stalled_intent(mock_agent, mock_queue):
    """An announced-but-unexecuted action must drive one more generate()."""
    history = []
    # Second iteration answers normally, so the turn ends there.
    mock_agent.provider.generate = MagicMock(
        side_effect=lambda *a, **k: _async_iter([StreamChunk(text="Done.")])
    )

    final_text, _log, _usage = await mock_agent._execute_tool_loop(
        initial_stream=_async_iter(
            [StreamChunk(text="I will visualize the network now.")]
        ),
        history=history,
        all_tools=[],
        queue=mock_queue,
        chat_id=1,
        network_id=1,
        session=None,
    )

    assert mock_agent.provider.generate.call_count == 1
    assert "Done." in final_text
    # The nudge is injected as a model turn plus a synthetic user turn.
    assert [m.role for m in history] == ["model", "user"]
    assert "calling the tool" in history[1].parts[0].text


@pytest.mark.asyncio
async def test_loop_grants_only_one_continuation(mock_agent, mock_queue):
    """The nudge must not ping-pong with the model for the whole budget."""
    mock_agent.provider.generate = MagicMock(
        side_effect=lambda *a, **k: _async_iter(
            [StreamChunk(text="I will calculate the centrality now.")]
        )
    )

    turn_state = new_turn_state(10)
    turn_state["network_id"] = 1

    await mock_agent._execute_tool_loop(
        initial_stream=_async_iter(
            [StreamChunk(text="I will calculate the centrality now.")]
        ),
        history=[],
        all_tools=[],
        queue=mock_queue,
        chat_id=1,
        network_id=1,
        session=None,
        turn_state=turn_state,
    )

    assert turn_state["continuations_granted"] == 1
    assert mock_agent.provider.generate.call_count == 1


@pytest.mark.asyncio
async def test_loop_does_not_nudge_a_question_to_the_user(mock_agent, mock_queue):
    """Proposing options and waiting is a complete turn, not a stall."""
    mock_agent.provider.generate = MagicMock()

    turn_state = new_turn_state(10)
    turn_state["network_id"] = 1
    text = "I can color by community or by degree. Which would you prefer?"

    final_text, _log, _usage = await mock_agent._execute_tool_loop(
        initial_stream=_async_iter([StreamChunk(text=text)]),
        history=[],
        all_tools=[],
        queue=mock_queue,
        chat_id=1,
        network_id=1,
        session=None,
        turn_state=turn_state,
    )

    mock_agent.provider.generate.assert_not_called()
    assert final_text == text


# --- tool execution ---

@pytest.mark.asyncio
async def test_execute_tools_and_update_history(mock_agent, mock_queue):
    """Tool execution appends model + tool turns and records the step log."""
    mock_agent._run_tool = AsyncMock(return_value=({"content": "ok"}, "completed", None))

    fc = FunctionCallData(name="test_tool", args={"param": 1}, call_id="call_1")
    history = []
    turn_state = new_turn_state(10)
    turn_state["network_id"] = 1

    step_log = await mock_agent._execute_tools_and_update_history(
        [fc], "Calling tool.", "", history, mock_queue,
        chat_id=1, turn_state=turn_state, session=None,
    )

    mock_agent._run_tool.assert_called_once()
    assert mock_agent._run_tool.call_args[0][0] == "test_tool"

    assert len(history) == 2
    assert history[0].role == "model"
    assert history[1].role == "tool"

    # tools_run is tallied by the audit POST_TOOL hook, replacing the old
    # loop_context["tools_executed"] flag.
    assert turn_state["tools_run"] == 1
    assert step_log["tool_calls"][0]["name"] == "test_tool"
    assert step_log["tool_calls"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_a_denied_tool_is_never_executed(mock_agent, mock_queue):
    """A PRE_TOOL denial must skip the call and hand the reason back as the result."""
    from app.services.llm.hooks import HookEvent, ToolCallDecision, registry

    mock_agent._run_tool = AsyncMock()
    reg_name = "test_denying_hook"
    registry.register(
        HookEvent.PRE_TOOL,
        lambda ctx: ToolCallDecision.deny("not allowed here"),
        priority=1,
        name=reg_name,
    )
    try:
        result, status, error, *_ = await mock_agent._run_tool_with_events(
            "test_tool", {"a": 1}, chat_id=1, session=None,
            queue=mock_queue, turn_state=new_turn_state(10),
        )
    finally:
        registry._hooks[HookEvent.PRE_TOOL] = [
            r for r in registry._hooks[HookEvent.PRE_TOOL] if r.name != reg_name
        ]

    mock_agent._run_tool.assert_not_called()
    assert status == "failed"
    assert result["error"] == "not allowed here"
    assert result["blocked_by"] == reg_name


@pytest.mark.asyncio
async def test_modified_arguments_are_reported_in_the_result(mock_agent, mock_queue):
    """The model must see what actually ran, not what it asked for."""
    from app.services.llm.hooks import HookEvent, ToolCallDecision, registry

    mock_agent._run_tool = AsyncMock(return_value=({"content": "ok"}, "completed", None))
    reg_name = "test_modifying_hook"
    registry.register(
        HookEvent.PRE_TOOL,
        lambda ctx: ToolCallDecision.modify({**ctx.args, "k": 1}, reason="k was clamped"),
        priority=1,
        name=reg_name,
    )
    try:
        result, status, *_ = await mock_agent._run_tool_with_events(
            "test_tool", {"k": -5}, chat_id=1, session=None,
            queue=mock_queue, turn_state=new_turn_state(10),
        )
    finally:
        registry._hooks[HookEvent.PRE_TOOL] = [
            r for r in registry._hooks[HookEvent.PRE_TOOL] if r.name != reg_name
        ]

    assert mock_agent._run_tool.call_args[0][1] == {"k": 1}
    # The note names the responsible hook, so the model can tell an argument
    # correction apart from a value the tool itself chose.
    assert result["_adjusted_arguments"] == "test_modifying_hook: k was clamped"


@pytest.mark.asyncio
async def test_loop_aborts_when_a_hook_sets_should_abort(mock_agent, mock_queue):
    """Repeated failures end the turn with an explanation instead of burning the budget."""
    mock_agent._run_tool = AsyncMock(return_value=({"error": "boom"}, "failed", "boom"))
    fc = FunctionCallData(name="test_tool", args={}, call_id="c1")
    mock_agent.provider.generate = MagicMock(
        side_effect=lambda *a, **k: _async_iter([StreamChunk(function_calls=[fc])])
    )

    turn_state = new_turn_state(10)
    turn_state["network_id"] = 1
    turn_state["failure_counts"] = {"test_tool": 99}  # already at the limit

    final_text, _log, _usage = await mock_agent._execute_tool_loop(
        initial_stream=_async_iter([StreamChunk(function_calls=[fc])]),
        history=[],
        all_tools=[],
        queue=mock_queue,
        chat_id=1,
        network_id=1,
        session=None,
        turn_state=turn_state,
    )

    assert turn_state["should_abort"] is True
    assert "I stopped before completing the request" in final_text
    # One iteration only: the abort check runs before the next generate().
    assert turn_state["iteration"] == 1


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
