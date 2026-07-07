import json
import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from common import models
from app.core.logging import get_logger

from . import local_tools, mcp_client
from .catalog import DEFAULT_PROVIDER
from .prompts import SYSTEM_INSTRUCTION
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


class GraphVisAgent:
    """
    Agent service for Graph Visualization (Single Agent Mode).
    Encapsulates the LLM interaction loop, tool execution, and state management.
    """

    def __init__(self, db: Any = None, provider_name: Optional[str] = None, model_name: Optional[str] = None):
        self.db = db
        # provider_name/model_name let a chat pin its own provider/model, overriding
        # the process-wide LLM_PROVIDER/GEMINI_MODEL/CLAUDE_MODEL env var defaults.
        self.provider_name = (provider_name or os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).lower()
        self.provider = _create_provider(self.provider_name, model_name)

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

    async def _check_and_handle_lazy_intent(
        self,
        text_content: str,
        history: List[LLMMessage],
        loop_context: Dict[str, Any],
        queue: Any,
        all_tools: List[ToolDefinition],
        session: Any,
    ) -> bool:
        """
        Detects if the model expressed intent to use a tool but didn't call it.
        If so, injects a user prompt to force the tool call.
        """
        keywords = ["visualize", "calculate", "import", "update", "change"]
        lower_text = text_content.lower()

        intent_detected = any(
            kw in lower_text and ("will" in lower_text or "let me" in lower_text)
            for kw in keywords
        )

        if intent_detected:
            logger.info(f"Lazy intent detected in text: '{text_content[:50]}...'")
            model_text = text_content if text_content else "I will now proceed."
            history.append(LLMMessage(role="model", parts=[LLMTextPart(text=model_text)]))
            history.append(LLMMessage(
                role="user",
                parts=[LLMTextPart(text="Please proceed with the action you described.")],
            ))
            return True

        return False

    async def process_turn(
        self,
        history: List[LLMMessage],
        queue: Any,
        chat_id: int,
        network_id: int,
    ) -> Tuple[str, List[Dict[str, Any]], UsageData]:
        """
        Orchestrates a single turn of the agent (User Input -> [Thoughts/Actions] -> Final Response).
        Returns:
            final_text: The string response to the user.
            execution_log: A list of steps containing tool calls and results for persistence.
            total_usage: Token usage accumulated across every provider.generate() call this turn.
        """
        logger.info(f"Starting agent turn for Chat ID: {chat_id}, Network ID: {network_id}")

        # 1. Prepare Tools
        all_tools = await self._get_all_tools()

        # Log what is being sent to the LLM
        self._log_history(history, iteration=0)

        # 2. Initial generation stream
        initial_stream = self.provider.generate(history, all_tools, SYSTEM_INSTRUCTION)

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
            )
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
    ) -> Tuple[str, List[Dict[str, Any]], UsageData]:
        """Manages the ReAct loop: Consumption -> Execution -> Observation -> Next Generation."""
        current_stream = initial_stream
        max_iterations = AGENT_MAX_ITERATIONS
        iteration = 0

        full_transcript = ""
        execution_log = []
        loop_context = {"network_id": network_id, "tools_executed": False}
        tool_call_counter = 0
        total_usage = UsageData()
        provider_name = self.provider_name

        while iteration < max_iterations:
            iteration += 1

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
                if await self._check_and_handle_lazy_intent(
                    full_transcript, history, loop_context, queue, all_tools, session
                ):
                    logger.info("Lazy Intent detected. Retrying generation...")
                    current_stream = self.provider.generate(history, all_tools, SYSTEM_INSTRUCTION)
                    continue

                has_text = bool(chunk_text.strip())

                if loop_context.get("tools_executed", False) and not has_text:
                    logger.info("Tools executed but no final text. Forcing summary generation.")
                    model_text = f"<thought>{chunk_thought}</thought>" if chunk_thought else "I have executed the tools."
                    history.append(LLMMessage(role="model", parts=[LLMTextPart(text=model_text)]))
                    summary_request = (
                        "The actions have been completed. Please provide a concise final report "
                        "summarizing what was done (e.g., 'Layout updated', 'Metrics calculated') "
                        "and any relevant findings."
                    )
                    history.append(LLMMessage(
                        role="user", parts=[LLMTextPart(text=summary_request)]
                    ))
                    current_stream = self.provider.generate(history, all_tools, SYSTEM_INSTRUCTION)
                    continue

                result_text = full_transcript
                if not result_text.strip():
                    return "I have processed your request.", execution_log, total_usage
                return result_text, execution_log, total_usage

            # Step C: Execute Tools (Parallelized)
            step_log = await self._execute_tools_and_update_history(
                function_calls, chunk_text, chunk_thought, history, queue, chat_id, loop_context, session
            )
            execution_log.append(step_log)

            # Step D: Inject Tool Markers into Transcript and Emit
            if step_log.get("tool_calls"):
                for _ in step_log["tool_calls"]:
                    marker = f"\n\n<tool_execution_marker index=\"{tool_call_counter}\"/>\n\n"
                    full_transcript += marker
                    await self._emit_message_chunk(queue, marker)
                    tool_call_counter += 1

            # Step E: Next Generation
            logger.info(f"--- LLM API Request (Iteration {iteration}) ---")
            self._log_history(history, iteration)
            current_stream = self.provider.generate(history, all_tools, SYSTEM_INSTRUCTION)

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
        loop_context: Dict[str, Any],
        session: Any,
    ) -> Dict[str, Any]:
        """Executes tools in PARALLEL, updates history, and returns a step log."""
        from datetime import datetime

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

        if function_calls:
            loop_context["tools_executed"] = True

        # Build model parts and task list
        tasks = []
        for fc in function_calls:
            model_parts.append(LLMFunctionCallPart(name=fc.name, args=fc.args, call_id=fc.call_id))
            step_record["tool_calls"].append({"name": fc.name, "args": fc.args})
            tasks.append(
                self._run_tool_with_events(
                    fc.name, fc.args, chat_id, loop_context["network_id"], session, queue
                )
            )

        # Execute in parallel; asyncio.gather preserves order
        results = await asyncio.gather(*tasks)

        # Build tool response parts and finalise the step log
        tool_parts = []
        for i, (result, status, error_msg, feature_name, started_at, completed_at) in enumerate(results):
            call_id = function_calls[i].call_id

            if status == "completed":
                await self._handle_side_effects(
                    feature_name, result, chat_id, queue, loop_context, session
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

    async def _run_tool_with_events(
        self,
        feature_name: str,
        args: Dict[str, Any],
        chat_id: int,
        network_id: int,
        session: Any,
        queue: Any,
    ) -> Tuple[Any, str, Optional[str], str, Any, Any]:
        """Wrapper to emit events and execute a single tool.
        Returns (result, status, error_msg, feature_name, started_at, completed_at).
        """
        from datetime import datetime, timezone

        started_at = datetime.now(timezone.utc)
        await self._emit_tool_event(queue, feature_name, "started", args)

        result, status, error_msg = await self._run_tool(
            feature_name, args, chat_id, network_id, session
        )

        completed_at = datetime.now(timezone.utc)
        await self._emit_tool_event(queue, feature_name, status, error_msg)

        return result, status, error_msg, feature_name, started_at, completed_at

    async def _run_tool(
        self,
        function_name: str,
        args: Dict[str, Any],
        chat_id: int,
        network_id: int,
        session: Any,
    ) -> Tuple[Any, str, Optional[str]]:
        """Actual execution wrapper."""
        try:
            if function_name in ["switch_to_main_network", "switch_to_parent_network"]:
                context = {"chat_id": chat_id, "db": self.db}
                result = await local_tools.execute_local_tool(function_name, args, context)
            else:
                if "network_id" not in args and network_id:
                    args["network_id"] = network_id
                result = await mcp_client.execute_tool(function_name, args, session=session)

            return result, "completed", None
        except Exception as e:
            logger.exception(f"Tool execution failed: {e}")
            return {"error": str(e)}, "failed", str(e)

    async def _handle_side_effects(
        self,
        function_name: str,
        result: Any,
        chat_id: int,
        queue: Any,
        loop_context: Dict[str, Any],
        session: Any,
    ):
        """Handles visualization updates and network ID switching."""
        if not isinstance(result, dict):
            return

        current_network_id = loop_context["network_id"]

        if "new_network_id" in result and result["new_network_id"] != current_network_id:
            new_id = result["new_network_id"]
            logger.info(f"Context switch: {current_network_id} -> {new_id}")
            vis_data = await self._auto_generate_visualization(new_id, queue, session)
            self._update_chat_state(chat_id, network_id=new_id, vis_data=vis_data)
            loop_context["network_id"] = new_id
            return

        if function_name in ["node_update_label"]:
            await self._auto_generate_visualization(current_network_id, queue, session)
            return

        vis_data = None
        if isinstance(result, dict):
            if "nodes" in result and "links" in result:
                vis_data = result
            elif function_name == "initialize_network" and "network" in result:
                vis_data = result["network"]

        if vis_data:
            await self._emit_render_update(queue, vis_data)
            self._update_chat_state(chat_id, vis_data=vis_data)

    async def _auto_generate_visualization(self, network_id: int, queue: Any, session: Any) -> Optional[Dict]:
        """Triggers visualization generation for a new network context."""
        try:
            vis_data = await mcp_client.execute_tool(
                "visualization_generate", {"network_id": network_id}, session=session
            )
            if isinstance(vis_data, dict) and "nodes" in vis_data:
                await self._emit_render_update(queue, vis_data)
                return vis_data
        except Exception as e:
            logger.error(f"Auto-vis failed for {network_id}: {e}")
            return None

    async def _get_all_tools(self) -> List[ToolDefinition]:
        mcp_tools = await mcp_client.get_tools()
        local_tool_defs = local_tools.get_local_tools()
        return mcp_tools + local_tool_defs

    async def _emit_message_chunk(self, queue: Any, text: str):
        await queue.put(
            {"event": "message_chunk", "data": json.dumps({"content": text})}
        )

    async def _emit_thinking_chunk(self, queue: Any, text: str):
        await queue.put(
            {"event": "thinking_stream", "data": json.dumps({"content": text})}
        )

    async def _emit_tool_event(self, queue: Any, tool: str, status: str, args_or_error: Any):
        data = {"tool": tool, "status": status}
        if status == "started":
            data["args"] = args_or_error
        else:
            data["error"] = args_or_error
        await queue.put({"event": "tool_execution", "data": json.dumps(data)})

    async def _emit_render_update(self, queue: Any, vis_data: Dict):
        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})

    async def _emit_usage_update(self, queue: Any, usage: UsageData, provider_name: str, model_name: str):
        from .pricing import estimate_cost_usd
        cost = estimate_cost_usd(
            model_name,
            usage.input_tokens,
            usage.output_tokens,
            usage.cached_input_tokens,
            provider=provider_name,
        )
        await queue.put({"event": "usage_update", "data": json.dumps({
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cached_input_tokens": usage.cached_input_tokens,
            "estimated_cost_usd": cost,
            "provider": provider_name,
            "model": model_name,
        })})

    def _update_chat_state(self, chat_id: int, network_id: int = None, vis_data: Dict = None):
        """Helper to update chat state in DB."""
        if not self.db:
            return
        chat = self.db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if chat:
            if network_id is not None:
                chat.network_id = network_id
            if vis_data is not None:
                chat.visualization_state = vis_data
            self.db.commit()

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
            initial_stream=agent.provider.generate(history, all_tools, SYSTEM_INSTRUCTION),
            history=history,
            all_tools=all_tools,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
            session=session,
        )
