import json
import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from app.core.logging import get_logger

from . import emitters, hooks, local_tools, mcp_client
from .catalog import DEFAULT_PROVIDER
from .prompts import build_system_instruction
from .providers.base import LLMProvider
from .providers.types import (
    FunctionCallData,
    LLMFunctionCallPart,
    LLMFunctionResponsePart,
    LLMMessage,
    LLMTextPart,
    StreamChunk,
    ToolDefinition,
    UsageData,
)

logger = get_logger(__name__)
load_dotenv()

# Max ReAct loop iterations per turn (each iteration = one LLM generate() call).
AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS") or 10)

# Register the builtin hooks once per process. Behaviour that used to be
# hardcoded in this module (auto-rendering, network switching, network_id
# injection, the stalled-intent nudge, the forced summary) now lives in
# hooks/builtin/ and is dispatched from the loop below.
hooks.load_builtin_hooks()


def _truncate_tool_result(result: Any, max_list_items: int = 15) -> Any:
    """Recursively truncates large lists in tool results to prevent LLM token overflow."""
    if isinstance(result, list):
        if len(result) > max_list_items:
            truncated = [_truncate_tool_result(item, max_list_items) for item in result[:max_list_items]]
            truncated.append(f"[{len(result) - max_list_items} items omitted for brevity]")
            return truncated
        return [_truncate_tool_result(item, max_list_items) for item in result]
    elif isinstance(result, dict):
        return {k: _truncate_tool_result(v, max_list_items) for k, v in result.items()}
    return result


def _create_provider(provider_name: str, model_name: Optional[str] = None) -> LLMProvider:
    """Instantiate the given LLM provider, optionally pinned to a specific model."""
    if provider_name == "anthropic":
        from .providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model_name=model_name)
    else:
        from .providers.google_genai import GoogleGenAIProvider
        return GoogleGenAIProvider(model_name=model_name)


def resolve_provider_name(provider_name: Optional[str] = None) -> str:
    """Resolve a chat's provider pin against the process-wide default."""
    return (provider_name or os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).lower()


def create_provider(
    provider_name: Optional[str] = None, model_name: Optional[str] = None
) -> LLMProvider:
    """Build a provider the way the agent does, for callers outside the ReAct loop
    (e.g. the one-shot title generation in titles.py)."""
    return _create_provider(resolve_provider_name(provider_name), model_name)


class GraphVisAgent:
    """
    Agent service for Graph Visualization (Single Agent Mode).
    Encapsulates the LLM interaction loop, tool execution, and state management.
    """

    def __init__(self, db: Any = None, provider_name: Optional[str] = None, model_name: Optional[str] = None):
        self.db = db
        # provider_name/model_name let a chat pin its own provider/model, overriding
        # the process-wide LLM_PROVIDER/GEMINI_MODEL/CLAUDE_MODEL env var defaults.
        self.provider_name = resolve_provider_name(provider_name)
        self.provider = _create_provider(self.provider_name, model_name)
        # Full system prompt for this turn. process_turn() appends the network
        # context summary so it is always present regardless of the user prompt.
        # The thinking protocol variant is chosen per the active provider/model's
        # native-thinking support (see LLMProvider.supports_native_thinking) so
        # providers with real thinking streams aren't also told to hand-write
        # <thought> tags in their text — see prompts.build_system_instruction.
        self.system_instruction = build_system_instruction(self.provider.supports_native_thinking)

    async def _consume_stream(
        self,
        stream: AsyncIterator[StreamChunk],
        queue: Any,
    ) -> Tuple[str, str, List[FunctionCallData], UsageData]:
        """Consume a provider stream, emit SSE events, and collect results."""
        text_content = ""
        thought_content = ""
        function_calls: List[FunctionCallData] = []
        usage = UsageData()

        try:
            async for chunk in stream:
                if chunk.thought:
                    thought_content += chunk.thought
                    await self._emit_thinking_chunk(queue, chunk.thought)
                if chunk.text:
                    text_content += chunk.text
                    await self._emit_message_chunk(queue, chunk.text)
                if chunk.function_calls:
                    function_calls.extend(chunk.function_calls)
                if chunk.usage:
                    # A single generate() call typically yields usage once, at the end,
                    # but sum defensively in case a provider yields it more than once.
                    usage.input_tokens += chunk.usage.input_tokens
                    usage.output_tokens += chunk.usage.output_tokens
                    usage.cached_input_tokens += chunk.usage.cached_input_tokens
        except Exception as e:
            logger.error(f"Error consuming stream: {e}")
            raise

        return text_content, thought_content, function_calls, usage

    async def process_turn(
        self,
        history: List[LLMMessage],
        queue: Any,
        chat_id: int,
        network_id: int,
        context_summary: str = "",
        user_text: str = "",
    ) -> Tuple[str, List[Dict[str, Any]], UsageData]:
        """
        Orchestrates a single turn of the agent (User Input -> [Thoughts/Actions] -> Final Response).
        Returns:
            final_text: The string response to the user.
            execution_log: A list of steps containing tool calls and results for persistence.
            total_usage: Token usage accumulated across every provider.generate() call this turn.
        """
        logger.info(f"Starting agent turn for Chat ID: {chat_id}, Network ID: {network_id}")

        # Per-turn state shared by every hook in this turn (counters, abort flag,
        # the active network id). Created once here and threaded through.
        turn_state = hooks.new_turn_state(AGENT_MAX_ITERATIONS)
        turn_state["network_id"] = network_id

        # Fix the system prompt for this turn: the network context summary and
        # any hook-contributed blocks are appended once here so every generate()
        # call in the loop shares the exact same system instruction (keeps
        # provider prompt caching intact).
        base_instruction = build_system_instruction(self.provider.supports_native_thinking)

        start_ctx = hooks.build_context(
            hooks.HookEvent.TURN_START,
            chat_id=chat_id,
            network_id=network_id,
            turn_state=turn_state,
            db=self.db,
            queue=queue,
            user_text=user_text,
        )
        hook_blocks = await hooks.registry.run_turn_start(start_ctx)

        sections = [base_instruction]
        if context_summary:
            sections.append(context_summary)
        sections.extend(hook_blocks)
        self.system_instruction = "\n\n---\n\n".join(sections)

        # 1. Prepare Tools
        all_tools = await self._get_all_tools()

        # Log what is being sent to the LLM
        self._log_history(history, iteration=0)

        # 2. Initial generation stream
        initial_stream = self.provider.generate(history, all_tools, self.system_instruction)

        # 3. Enter Tool Execution Loop within Session Scope
        async with mcp_client.session_scope() as session:
            final_text, execution_log, total_usage = await self._execute_tool_loop(
                initial_stream=initial_stream,
                history=history,
                all_tools=all_tools,
                queue=queue,
                chat_id=chat_id,
                network_id=network_id,
                session=session,
                turn_state=turn_state,
            )

        end_ctx = hooks.build_context(
            hooks.HookEvent.TURN_END,
            chat_id=chat_id,
            network_id=turn_state.get("network_id") or network_id,
            turn_state=turn_state,
            db=self.db,
            queue=queue,
        )
        await hooks.registry.run_turn_end(end_ctx)

        return final_text, execution_log, total_usage

    async def _execute_tool_loop(
        self,
        initial_stream: AsyncIterator[StreamChunk],
        history: List[LLMMessage],
        all_tools: List[ToolDefinition],
        queue: Any,
        chat_id: int,
        network_id: int,
        session: Any,
        turn_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[Dict[str, Any]], UsageData]:
        """Manages the ReAct loop: Consumption -> Execution -> Observation -> Next Generation."""
        current_stream = initial_stream
        max_iterations = AGENT_MAX_ITERATIONS
        iteration = 0

        if turn_state is None:
            turn_state = hooks.new_turn_state(max_iterations)
            turn_state["network_id"] = network_id

        full_transcript = ""
        execution_log = []
        tool_call_counter = 0
        total_usage = UsageData()
        provider_name = self.provider_name

        while iteration < max_iterations:
            iteration += 1
            turn_state["iteration"] = iteration

            # Step A: Consume Stream
            chunk_text, chunk_thought, function_calls, iter_usage = await self._consume_stream(
                current_stream, queue
            )

            # Iterations are separate generate() calls, each with its own full input
            # context, so input/cached tokens are SUMMED across iterations.
            total_usage.input_tokens += iter_usage.input_tokens
            total_usage.output_tokens += iter_usage.output_tokens
            total_usage.cached_input_tokens += iter_usage.cached_input_tokens
            if iter_usage.input_tokens or iter_usage.output_tokens:
                await self._emit_usage_update(queue, total_usage, provider_name, self.provider.model_name)

            if chunk_thought:
                full_transcript += f"<thought>{chunk_thought}</thought>\n\n"
            if chunk_text:
                full_transcript += chunk_text

            # Step B: Check for Completion or Tool Calls
            if not function_calls:
                # The turn is about to end. Hooks get one chance to say it should
                # not: an announced-but-unexecuted action, or tool work with no
                # closing report. See hooks/builtin/intent.py.
                no_call_ctx = hooks.build_context(
                    hooks.HookEvent.NO_TOOL_CALLS,
                    chat_id=chat_id,
                    network_id=turn_state.get("network_id") or network_id,
                    turn_state=turn_state,
                    db=self.db,
                    queue=queue,
                    session=session,
                    assistant_text=chunk_text,
                    thought_text=chunk_thought,
                )
                continuation = await hooks.registry.run_no_tool_calls(no_call_ctx)

                if continuation:
                    turn_state["continuation"] = None
                    turn_state["continuations_granted"] = (
                        turn_state.get("continuations_granted", 0) + 1
                    )
                    logger.info(
                        f"Continuation requested by {continuation.get('requested_by')}; regenerating"
                    )
                    history.append(LLMMessage(
                        role="model",
                        parts=[LLMTextPart(text=continuation["model_text"] or "I will now proceed.")],
                    ))
                    history.append(LLMMessage(
                        role="user", parts=[LLMTextPart(text=continuation["prompt"])]
                    ))
                    current_stream = self.provider.generate(history, all_tools, self.system_instruction)
                    continue

                result_text = full_transcript
                if not result_text.strip():
                    return "I have processed your request.", execution_log, total_usage
                return result_text, execution_log, total_usage

            # Step C: Execute Tools (Parallelized)
            step_log = await self._execute_tools_and_update_history(
                function_calls, chunk_text, chunk_thought, history, queue, chat_id, turn_state, session
            )
            execution_log.append(step_log)

            # Step D: Inject Tool Markers into Transcript and Emit
            if step_log.get("tool_calls"):
                for _ in step_log["tool_calls"]:
                    marker = f"\n\n<tool_execution_marker index=\"{tool_call_counter}\"/>\n\n"
                    full_transcript += marker
                    await self._emit_message_chunk(queue, marker)
                    tool_call_counter += 1

            # Step E: Honour an abort requested by a hook (e.g. repeated failures
            # of the same tool) before spending another generate() call.
            if turn_state.get("should_abort"):
                reason = turn_state.get("abort_reason") or "the agent stopped early"
                logger.warning(f"Turn aborted after iteration {iteration}: {reason}")
                abort_note = (
                    f"\n\nI stopped before completing the request: {reason}"
                )
                await self._emit_message_chunk(queue, abort_note)
                return full_transcript + abort_note, execution_log, total_usage

            # Step F: Next Generation
            logger.info(f"--- LLM API Request (Iteration {iteration}) ---")
            self._log_history(history, iteration)
            current_stream = self.provider.generate(history, all_tools, self.system_instruction)

        if not full_transcript.strip():
            return (
                "I have completed the requested actions, but the process reached its step limit before generating a final report.",
                execution_log,
                total_usage,
            )

        return full_transcript, execution_log, total_usage

    async def _execute_tools_and_update_history(
        self,
        function_calls: List[FunctionCallData],
        text_content: str,
        thought_content: str,
        history: List[LLMMessage],
        queue: Any,
        chat_id: int,
        turn_state: Dict[str, Any],
        session: Any,
    ) -> Dict[str, Any]:
        """Executes tools in PARALLEL, updates history, and returns a step log."""

        # Model turn parts: optional text/thought prefix followed by function call parts
        model_parts = []
        model_response_text = ""
        if thought_content:
            model_response_text += f"<thought>{thought_content}</thought>\n\n"
        if text_content:
            model_response_text += text_content
        if model_response_text:
            model_parts.append(LLMTextPart(text=model_response_text))

        log_thought = thought_content if thought_content else text_content
        step_record: Dict[str, Any] = {
            "step_type": "tool_execution",
            "thought": log_thought,
            "tool_calls": [],
        }

        # Build model parts and task list
        tasks = []
        for fc in function_calls:
            model_parts.append(LLMFunctionCallPart(name=fc.name, args=fc.args, call_id=fc.call_id))
            step_record["tool_calls"].append({"name": fc.name, "args": fc.args})
            tasks.append(
                self._run_tool_with_events(
                    fc.name, fc.args, chat_id, session, queue, turn_state
                )
            )

        # Execute in parallel; asyncio.gather preserves order
        results = await asyncio.gather(*tasks)

        # Build tool response parts and finalise the step log
        tool_parts = []
        for i, (result, status, error_msg, feature_name, started_at, completed_at) in enumerate(results):
            call_id = function_calls[i].call_id

            # POST_TOOL / TOOL_ERROR run sequentially here, after every tool in
            # this batch has returned, so a hook that switches the active network
            # cannot race the other calls of the same batch.
            event = (
                hooks.HookEvent.POST_TOOL
                if status == "completed"
                else hooks.HookEvent.TOOL_ERROR
            )
            await self._dispatch_tool_hooks(
                event,
                tool_name=feature_name,
                args=function_calls[i].args,
                result=result,
                error=error_msg,
                chat_id=chat_id,
                session=session,
                queue=queue,
                turn_state=turn_state,
            )

            truncated_result = _truncate_tool_result(result)

            tool_parts.append(LLMFunctionResponsePart(
                name=feature_name, response=truncated_result, call_id=call_id
            ))

            for call_record in step_record["tool_calls"]:
                if call_record["name"] == feature_name and "result" not in call_record:
                    call_record["result"] = truncated_result
                    call_record["status"] = status
                    call_record["error"] = error_msg
                    call_record["started_at"] = started_at
                    call_record["completed_at"] = completed_at
                    break

        history.append(LLMMessage(role="model", parts=model_parts))
        history.append(LLMMessage(role="tool", parts=tool_parts))

        return step_record

    async def _dispatch_tool_hooks(
        self,
        event: "hooks.HookEvent",
        *,
        tool_name: str,
        args: Dict[str, Any],
        chat_id: int,
        session: Any,
        queue: Any,
        turn_state: Dict[str, Any],
        result: Any = None,
        error: Optional[str] = None,
    ) -> Any:
        """Build a HookContext for a tool-scoped event and run the matching hooks."""
        ctx = hooks.build_context(
            event,
            chat_id=chat_id,
            network_id=turn_state.get("network_id") or 0,
            turn_state=turn_state,
            db=self.db,
            queue=queue,
            session=session,
            tool_name=tool_name,
            args=args,
            result=result,
            error=error,
        )
        if event is hooks.HookEvent.PRE_TOOL:
            return await hooks.registry.run_pre_tool(ctx)
        if event is hooks.HookEvent.POST_TOOL:
            return await hooks.registry.run_post_tool(ctx)
        if event is hooks.HookEvent.TOOL_ERROR:
            return await hooks.registry.run_tool_error(ctx)
        raise ValueError(f"{event} is not a tool-scoped hook event")

    async def _run_tool_with_events(
        self,
        feature_name: str,
        args: Dict[str, Any],
        chat_id: int,
        session: Any,
        queue: Any,
        turn_state: Dict[str, Any],
    ) -> Tuple[Any, str, Optional[str], str, Any, Any]:
        """Run PRE_TOOL hooks, then the tool, emitting SSE events around it.
        Returns (result, status, error_msg, feature_name, started_at, completed_at).
        """
        from datetime import datetime, timezone

        started_at = datetime.now(timezone.utc)
        await self._emit_tool_event(queue, feature_name, "started", args)

        decision = await self._dispatch_tool_hooks(
            hooks.HookEvent.PRE_TOOL,
            tool_name=feature_name,
            args=dict(args),
            chat_id=chat_id,
            session=session,
            queue=queue,
            turn_state=turn_state,
        )

        if decision.action == "deny":
            # Not an exception: the refusal is handed back as the tool result so
            # the model reads the reason and can correct itself next iteration.
            turn_state["tools_blocked"] = turn_state.get("tools_blocked", 0) + 1
            reason = decision.reason or "This call was blocked by a policy hook."
            logger.info(f"Tool '{feature_name}' blocked by {decision.hook_name}: {reason}")
            completed_at = datetime.now(timezone.utc)
            await self._emit_tool_event(queue, feature_name, "failed", reason)
            return (
                {"error": reason, "blocked_by": decision.hook_name},
                "failed",
                reason,
                feature_name,
                started_at,
                completed_at,
            )

        effective_args = args
        modification_note = None
        if decision.action == "modify" and decision.args is not None:
            turn_state["tools_modified"] = turn_state.get("tools_modified", 0) + 1
            effective_args = decision.args
            modification_note = decision.reason

        result, status, error_msg = await self._run_tool(
            feature_name, effective_args, chat_id, session, turn_state
        )

        # Tell the model when its arguments were adjusted, so it reports what
        # actually ran rather than what it asked for.
        if modification_note and status == "completed":
            if isinstance(result, dict):
                result = {**result, "_adjusted_arguments": modification_note}
            else:
                result = {"result": result, "_adjusted_arguments": modification_note}

        completed_at = datetime.now(timezone.utc)
        await self._emit_tool_event(queue, feature_name, status, error_msg)

        return result, status, error_msg, feature_name, started_at, completed_at

    async def _run_tool(
        self,
        function_name: str,
        args: Dict[str, Any],
        chat_id: int,
        session: Any,
        turn_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, str, Optional[str]]:
        """Actual execution wrapper.

        `network_id` defaulting used to happen here; it is now the
        `normalize_network_id` PRE_TOOL hook.
        """
        try:
            if local_tools.is_local_tool(function_name):
                context = {"chat_id": chat_id, "db": self.db, "turn_state": turn_state or {}}
                result = await local_tools.execute_local_tool(function_name, args, context)
            else:
                result = await mcp_client.execute_tool(function_name, args, session=session)

            return result, "completed", None
        except Exception as e:
            logger.exception(f"Tool execution failed: {e}")
            return {"error": str(e)}, "failed", str(e)

    async def _get_all_tools(self) -> List[ToolDefinition]:
        mcp_tools = await mcp_client.get_tools()
        local_tool_defs = local_tools.get_local_tools()
        return mcp_tools + local_tool_defs

    # Emission is shared with the hooks (which have a queue but no agent
    # instance), so the event shapes live in emitters.py. These stay as methods
    # because the loop reads more clearly with them.

    async def _emit_message_chunk(self, queue: Any, text: str):
        await emitters.emit_message_chunk(queue, text)

    async def _emit_thinking_chunk(self, queue: Any, text: str):
        await emitters.emit_thinking_chunk(queue, text)

    async def _emit_tool_event(self, queue: Any, tool: str, status: str, args_or_error: Any):
        await emitters.emit_tool_event(queue, tool, status, args_or_error)

    async def _emit_render_update(self, queue: Any, vis_data: Dict):
        await emitters.emit_render_update(queue, vis_data)

    async def _emit_usage_update(self, queue: Any, usage: UsageData, provider_name: str, model_name: str):
        await emitters.emit_usage_update(queue, usage, provider_name, model_name)

    def _log_history(self, history: List[LLMMessage], iteration: int):
        """Helper to log the exact data being sent to the LLM context.

        Message contents (user text, tool args/results) are user data, so the
        full dump is DEBUG-only; INFO gets just the size summary.
        """
        logger.info(
            f"Context sent to LLM (iteration {iteration}): {len(history)} history messages"
        )
        if not logger.isEnabledFor(logging.DEBUG):
            return
        for i, msg in enumerate(history):
            logger.debug(f"  [{i}] Role: {msg.role}")
            for part in msg.parts:
                if isinstance(part, LLMTextPart):
                    logger.debug(f"      TextPart: {part.text[:200].replace(chr(10), ' ')}...")
                elif isinstance(part, LLMFunctionCallPart):
                    logger.debug(f"      ToolCallPart: {part.name}({part.args})")
                elif isinstance(part, LLMFunctionResponsePart):
                    resp_str = json.dumps(part.response, ensure_ascii=False)
                    # Limit log output to avoid console spam, but show structure
                    logger.debug(f"      ToolResponsePart: {part.name} -> {resp_str[:300]}...")
        logger.debug("-" * 50)


# --- Legacy/Functional Interface for compatibility with existing route handlers ---

async def execute_tool_loop(
    initial_response, network_id, history, queue, tool_config, chat_id, db
):
    """Legacy entry point. Instantiates GraphVisAgent and runs the process."""
    agent = GraphVisAgent(db)
    all_tools = await agent._get_all_tools()

    async with mcp_client.session_scope() as session:
        return await agent._execute_tool_loop(
            initial_stream=agent.provider.generate(history, all_tools, agent.system_instruction),
            history=history,
            all_tools=all_tools,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
            session=session,
        )
