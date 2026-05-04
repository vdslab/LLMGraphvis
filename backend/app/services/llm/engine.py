import json
import asyncio
import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log
import logging

from common import models
from app.core.logging import get_logger

from . import local_tools, mcp_client
from .prompts import SYSTEM_INSTRUCTION

logger = get_logger(__name__)
load_dotenv()



def is_retryable_error(exception):
    """Check if the exception is a transient error suitable for retry."""
    try:
        # Check for HTTP status codes (429, 5xx)
        code = getattr(exception, "code", None)
        status = getattr(exception, "status", None)
        
        retryable_codes = [429, 500, 502, 503, 504]
        if code in retryable_codes:
            return True
            
        # Check for specific status strings
        # User error: 'status': 'RESOURCE_EXHAUSTED'
        retryable_statuses = ["RESOURCE_EXHAUSTED", "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"]
        if str(status) in retryable_statuses:
            return True

        # Fallback: Check message content
        msg = str(exception).lower()
        if "resource exhausted" in msg or "internal server error" in msg or "service unavailable" in msg:
            return True
            
    except Exception:
        pass
    return False


class GraphVisAgent:
    """
    Agent service for Graph Visualization (Single Agent Mode).
    Encapsulates the LLM interaction loop, tool execution, and state management.
    """

    def __init__(self, db: Any = None):
        self.db = db
        self.client = self._initialize_client()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _initialize_client(self) -> genai.Client:
        project_id = os.getenv("VERTEX_PROJECT_ID")
        location = os.getenv("VERTEX_LOCATION", "us-central1")
        api_key = os.getenv("GOOGLE_API_KEY")

        if project_id:
            msg = f"🟢 Using Vertex AI (Project: {project_id}, Location: {location})"
            logger.info(msg)
            print(msg) # Immediate console feedback
            return genai.Client(
                vertexai=True, project=project_id, location=location
            )
        else:
            msg = "🔵 Using Google AI Studio (API Key)"
            logger.info(msg)
            print(msg) # Immediate console feedback
            return genai.Client(api_key=api_key)

    @retry(
        retry=retry_if_exception(is_retryable_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _gemini_generate(
        self,
        history: List[types.Content],
        tools: List[types.Tool],
        tool_config: Optional[types.ToolConfig] = None,
    ):
        """Generates content stream from Gemini."""
        return await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=history,
            config=types.GenerateContentConfig(
                tools=tools,
                tool_config=tool_config,
                system_instruction=SYSTEM_INSTRUCTION,
                thinking_config=types.ThinkingConfig(thinking_budget=2048) if "thinking" in self.model_name else None,
            ),
        )

    async def _consume_stream(self, response: Any, queue: Any) -> Tuple[str, str, List[types.FunctionCall]]:
        """Consumes the stream and emits events."""
        text_content = ""
        thought_content = ""
        function_calls = []
        
        in_simulated_thought = False
        
        try:
            async for chunk in response:
                if chunk.candidates:
                    cand = chunk.candidates[0]
                    if cand.content and cand.content.parts:
                        for part in cand.content.parts:
                            # Handle Thinking (if supported by model/SDK)
                            is_thought = False
                            current_thought_text = ""

                            # Check if 'thought' is a string content (earlier SDKs/Models)
                            if hasattr(part, "thought") and isinstance(part.thought, str) and part.thought:
                                is_thought = True
                                current_thought_text = part.thought
                            
                            # Check if 'thought' is a boolean flag (Gemini 2.5 style according to some docs)
                            elif hasattr(part, "thought") and isinstance(part.thought, bool) and part.thought:
                                is_thought = True
                                if part.text:
                                    current_thought_text = part.text

                            if is_thought:
                                thought_content += current_thought_text
                                await self._emit_thinking_chunk(queue, current_thought_text)
                            elif part.text:
                                # Parsing <thought> tags in text (Simulated Thinking)
                                txt = part.text
                                
                                # Check for start tag if not in thought
                                if not in_simulated_thought:
                                    if "<thought>" in txt:
                                        valid_text, rest = txt.split("<thought>", 1)
                                        if valid_text:
                                            text_content += valid_text
                                            await self._emit_message_chunk(queue, valid_text)
                                        in_simulated_thought = True
                                        txt = rest # Continue processing as thought
                                    else:
                                        # Standard text
                                        text_content += txt
                                        await self._emit_message_chunk(queue, txt)
                                        continue
                                
                                # Inside simulated thought
                                if in_simulated_thought:
                                    if "</thought>" in txt:
                                        t_content, rest_text = txt.split("</thought>", 1)
                                        thought_content += t_content
                                        await self._emit_thinking_chunk(queue, t_content)
                                        in_simulated_thought = False
                                        
                                        if rest_text:
                                            text_content += rest_text
                                            await self._emit_message_chunk(queue, rest_text)
                                    else:
                                        # All content is thought
                                        thought_content += txt
                                        await self._emit_thinking_chunk(queue, txt)

                            if part.function_call:
                                function_calls.append(part.function_call)
        except Exception as e:
            logger.error(f"Error consuming stream: {e}")
            raise e
            
        return text_content, thought_content, function_calls

    async def _check_and_handle_lazy_intent(
        self,
        text_content: str,
        history: List[types.Content],
        loop_context: Dict[str, Any],
        queue: Any,
        all_tools: List[types.Tool],
        tool_config: Optional[types.ToolConfig],
        session: Any
    ) -> bool:
        """
        Detects if the model expressed intent to use a tool but didn't call it.
        If so, injects a user prompt to force the tool call.
        """
        # Simple keyword matching for Lazy Intent (could be improved with another LLM call)
        # Check if text contains "I will" or "let me" followed by "visualize", "calculate", etc.
        # and NO function calls were made (handled by caller).
        
        keywords = ["visualize", "calculate", "import", "update", "change"]
        lower_text = text_content.lower()
        
        intent_detected = False
        for kw in keywords:
            if kw in lower_text and ("will" in lower_text or "let me" in lower_text):
                intent_detected = True
                break
        
        if intent_detected:
            logger.info(f"Lazy intent detected in text: '{text_content[:50]}...'")
            # Must append the model's response before injecting user prompt to maintain turn alternation
            model_parts = []
            if text_content:
                model_parts.append(types.Part.from_text(text=text_content))
            else:
                model_parts.append(types.Part.from_text(text="I will now proceed."))
            history.append(types.Content(role="model", parts=model_parts))
            
            # Inject prompt
            history.append(types.Content(
                role="user", 
                parts=[types.Part.from_text(text="Please proceed with the action you described.")]
            ))
            return True
            
        return False

    async def process_turn(
        self,
        history: List[types.Content],
        queue: Any,
        chat_id: int,
        network_id: int,
        tool_config: Optional[types.ToolConfig] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Orchestrates a single turn of the agent (User Input -> [Thoughts/Actions] -> Final Response).
        Returns:
            final_text: The string response to the user.
            execution_log: A list of steps containing tool calls and results for persistence.
        """
        logger.info(f"Starting agent turn for Chat ID: {chat_id}, Network ID: {network_id}")
        
        # 1. Prepare Tools
        all_tools = await self._get_all_tools()

        # 2. Generate Initial Response Stream (using retry-wrapped method)
        current_response = await self._gemini_generate(history, all_tools, tool_config)

        # 3. Enter Tool Execution Loop within Session Scope
        # This ensures we reuse the same MCP connection for all tool calls in this turn
        async with mcp_client.session_scope() as session:
            final_text, execution_log = await self._execute_tool_loop(
                initial_response=current_response,
                history=history,
                all_tools=all_tools,
                tool_config=tool_config,
                queue=queue,
                chat_id=chat_id,
                network_id=network_id,
                session=session,
            )
            return final_text, execution_log

    async def _execute_tool_loop(
        self,
        initial_response: Any,
        history: List[types.Content],
        all_tools: List[types.Tool],
        tool_config: Optional[types.ToolConfig],
        queue: Any,
        chat_id: int,
        network_id: int,
        session: Any, # ClientSession
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Manages the ReAct loop: Consumption -> Execution -> Observation -> Next Generation.
        """
        current_response = initial_response
        max_iterations = 10
        iteration = 0
        
        # We build the full transcript (Thoughts + Text) chronologically
        full_transcript = ""
        
        # Log of all actions taken in this turn
        execution_log = []

        # Using a context object to track state across the loop (e.g. network_id updates)
        loop_context = {"network_id": network_id, "tools_executed": False}

        tool_call_counter = 0

        while iteration < max_iterations:
            iteration += 1
            
            # Step A: Consume Stream
            # Returns aggregated text and a list of tool calls
            chunk_text, chunk_thought, function_calls = await self._consume_stream(current_response, queue)
            
            if chunk_thought:
                full_transcript += f"<thought>{chunk_thought}</thought>\n\n"
            
            if chunk_text:
                full_transcript += chunk_text

            # Step B: Check for Completion or Tool Calls
            if not function_calls:
                # No tools called. Check for "Lazy Intent" (Reflection)
                if await self._check_and_handle_lazy_intent(
                    full_transcript, history, loop_context, queue, all_tools, tool_config, session
                ):
                    # Lazy Intent Detected & Alert Added to History.
                    logger.info("Lazy Intent detected. Retrying generation...")
                    current_response = await self._gemini_generate(history, all_tools, tool_config)
                    continue

                # NEW: If tools were executed but we have no meaningful response text, force a summary.
                # We check loop_context to see if we did anything.
                # Use a cleaner check for text content (ignoring thoughts)
                has_text = bool(chunk_text.strip())
                
                if loop_context.get("tools_executed", False) and not has_text:
                    logger.info("Tools executed but no final text. Forcing summary generation.")
                    # Append a model turn first to acknowledge the tools and maintain alternation
                    model_parts = []
                    if chunk_thought:
                        model_parts.append(types.Part.from_text(text=f"<thought>{chunk_thought}</thought>"))
                    else:
                        model_parts.append(types.Part.from_text(text="I have executed the tools."))
                    history.append(types.Content(role="model", parts=model_parts))
                    
                    # We inject a user prompt to force the model to summarize.
                    summary_request = "The actions have been completed. Please provide a concise final report summarizing what was done (e.g., 'Layout updated', 'Metrics calculated') and any relevant findings."
                    history.append(types.Content(role="user", parts=[types.Part.from_text(text=summary_request)]))
                    
                    # Generate again
                    current_response = await self._gemini_generate(history, all_tools, tool_config)
                    continue
                
                # If we are truly done (no tools, no lazy intent), exit.
                result_text = full_transcript
                
                if not result_text.strip():
                    return "I have processed your request.", execution_log
                    
                return result_text, execution_log

            # Step C: Execute Tools (Parallelized)
            step_log = await self._execute_tools_and_update_history(
                function_calls, chunk_text, chunk_thought, history, queue, chat_id, loop_context, session
            )
            execution_log.append(step_log)

            # Step D: Inject Tool Markers into Transcript and Emit
            # This allows the frontend to render the tools chronologically in the stream
            if step_log.get("tool_calls"):
                for _ in step_log["tool_calls"]:
                    marker = f"\n\n<tool_execution_marker index=\"{tool_call_counter}\"/>\n\n"
                    full_transcript += marker
                    await self._emit_message_chunk(queue, marker)
                    tool_call_counter += 1
            
            # Step E: Next Generation
            logger.info(f"--- Gemini API Request (Iteration {iteration}) ---")
            current_response = await self._gemini_generate(history, all_tools, tool_config)

        if not full_transcript.strip():
             return "I have completed the requested actions, but the process reached its step limit before generating a final report.", execution_log

        return full_transcript, execution_log

    # ... (retry decorators omitted, kept as is in original file) ...
    # Note: I am not replacing _gemini_generate or _consume_stream, assuming they are outside the range or handled separately.
    # The tool replacement range ends at 458, which is _handle_side_effects.
    
    # Need to skip down to _execute_tools_and_update_history replacement.
    
    # ...

    async def _execute_tools_and_update_history(
        self,
        function_calls: List[Any],
        text_content: str,
        thought_content: str,  # Accepted thought content
        history: List[types.Content],
        queue: Any,
        chat_id: int,
        loop_context: Dict[str, Any],
        session: Any,
    ) -> Dict[str, Any]:
        """
        Executes tools in PARALLEL and updates history.
        Returns a dict representing this step's execution log.
        """
        import asyncio
        from datetime import datetime
        
        function_calls_parts = []
        function_responses_parts = []
        
        # For the log
        # Prioritize thought_content for the 'thought' field in execution logs
        log_thought = thought_content if thought_content else text_content
        
        step_record = {
            "step_type": "tool_execution",
            "thought": log_thought,
            "tool_calls": []
        }

        # Update History with Context (Thought + Text)
        # We need to reconstruct the message as the model generated it for the history
        model_response_text = ""
        if thought_content:
            model_response_text += f"<thought>{thought_content}</thought>\n\n"
        if text_content:
            model_response_text += text_content
            
        if model_response_text:
            function_calls_parts.append(types.Part.from_text(text=model_response_text))

        if function_calls:
            loop_context["tools_executed"] = True

        # 1. Prepare Tasks
        tasks = []
        for fc in function_calls:
            function_calls_parts.append(types.Part(function_call=fc))
            feature_name = fc.name
            args = dict(fc.args)

            # Record in log (Placeholder, will fill result later)
            step_record["tool_calls"].append({
                "name": feature_name,
                "args": args
            })

            # Create Task
            tasks.append(
                self._run_tool_with_events(
                    feature_name, args, chat_id, loop_context["network_id"], session, queue
                )
            )

        # 2. Execute Parallel
        # Returns list of (result, status, error_msg, feature_name, started_at, completed_at)
        results = await asyncio.gather(*tasks)

        # 3. Process Results (Sequential Side Effects)
        for result, status, error_msg, feature_name, started_at, completed_at in results:
            
            # Handle Side Effects (Visualization, Context Switch)
            # We must do this sequentially to avoid race conditions on DB/loop_context
            if status == "completed":
                await self._handle_side_effects(
                    feature_name, result, chat_id, queue, loop_context, session
                )

            # Collect Response
            function_responses_parts.append(
                types.Part.from_function_response(name=feature_name, response=result)
            )

            # Update log with result and timing
            for call_record in step_record["tool_calls"]:
                if call_record["name"] == feature_name and "result" not in call_record:
                    call_record["result"] = result
                    call_record["status"] = status
                    call_record["error"] = error_msg
                    call_record["started_at"] = started_at
                    call_record["completed_at"] = completed_at
                    break

        # Update History with valid turn structure
        history.append(types.Content(role="model", parts=function_calls_parts))
        history.append(types.Content(role="tool", parts=function_responses_parts))
        
        return step_record

    async def _run_tool_with_events(
        self, feature_name: str, args: Dict[str, Any], chat_id: int, network_id: int, session: Any, queue: Any
    ) -> Tuple[Any, str, Optional[str], str, Any, Any]:
        """
        Wrapper to handle event emission and execution for a single tool.
        Returns (result, status, error_msg, feature_name, started_at, completed_at)
        """
        from datetime import datetime, timezone
        
        started_at = datetime.now(timezone.utc)
        
        # Emit "Started" event
        await self._emit_tool_event(queue, feature_name, "started", args)

        # Execute
        result, status, error_msg = await self._run_tool(
            feature_name, args, chat_id, network_id, session
        )
        
        completed_at = datetime.now(timezone.utc)
        
        # Emit "Completed" event
        await self._emit_tool_event(queue, feature_name, status, error_msg)
        
        return result, status, error_msg, feature_name, started_at, completed_at

    async def _run_tool(
        self, function_name: str, args: Dict[str, Any], chat_id: int, network_id: int, session: Any
    ) -> Tuple[Any, str, Optional[str]]:
        """Actual execution wrapper."""
        try:
            if function_name in ["switch_to_main_network", "switch_to_parent_network"]:
                # Local Tool
                context = {"chat_id": chat_id, "db": self.db}
                result = await local_tools.execute_local_tool(function_name, args, context)
            else:
                # MCP Tool
                if "network_id" not in args and network_id:
                    args["network_id"] = network_id
                # Pass session!
                result = await mcp_client.execute_tool(function_name, args, session=session)
            
            return result, "completed", None
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            traceback.print_exc()
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
        """Handles Visualization updates and Network ID switching."""
        if not isinstance(result, dict):
            return

        current_network_id = loop_context["network_id"]

        # 1. Context Switching
        if "new_network_id" in result and result["new_network_id"] != current_network_id:
            new_id = result["new_network_id"]
            logger.info(f"Context switch: {current_network_id} -> {new_id}")
            
            # Auto-Visualize
            vis_data = await self._auto_generate_visualization(new_id, queue, session)
            
            # Update DB
            self._update_chat_state(chat_id, network_id=new_id, vis_data=vis_data)
            
            # Update Loop Context
            loop_context["network_id"] = new_id
            return

        # 2. Explicit Visualization Triggers (Edit operations)
        if function_name in ["update_node_label"]:
            await self._auto_generate_visualization(current_network_id, queue, session)
            return

        # 3. Visualization Updates
        vis_data = None

        
        # Check if result looks like visualization data (Duck Typing)
        if isinstance(result, dict):
            if "nodes" in result and "links" in result:
                vis_data = result
            elif function_name == "initialize_network" and "network" in result:
                vis_data = result["network"]

        if vis_data:
            await self._emit_render_update(queue, vis_data)
            # Save state
            self._update_chat_state(chat_id, vis_data=vis_data)

    async def _auto_generate_visualization(self, network_id: int, queue: Any, session: Any) -> Optional[Dict]:
        """Triggers visualization generation for a new network context."""
        try:
            vis_data = await mcp_client.execute_tool(
                "generate_visualization", {"network_id": network_id}, session=session
            )
            if isinstance(vis_data, dict) and "nodes" in vis_data:
                await self._emit_render_update(queue, vis_data)
                return vis_data
        except Exception as e:
            logger.error(f"Auto-vis failed for {network_id}: {e}")
            return None

    async def _get_all_tools(self) -> List[types.Tool]:
        mcp_tools = await mcp_client.get_tools_as_gemini_functions()
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


# --- Legacy/Functional Interface for compatibility with existing route handlers ---

async def execute_tool_loop(
    initial_response, network_id, history, queue, tool_config, chat_id, db
):
    """
    Legacy entry point. Instantiates GraphVisAgent and runs the process.
    """
    agent = GraphVisAgent(db)
    
    all_tools = await agent._get_all_tools()
    
    async with mcp_client.session_scope() as session:
        return await agent._execute_tool_loop(
            initial_response=initial_response,
            history=history,
            all_tools=all_tools,
            tool_config=tool_config,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
            session=session
        )
