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
            logger.info(
                f"Using Vertex AI with Project ID: {project_id}, Location: {location}"
            )
            return genai.Client(
                vertexai=True, project=project_id, location=location
            )
        else:
            logger.info("Using Google AI Studio with API Key")
            return genai.Client(api_key=api_key)


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
        final_text_content = ""
        
        # Log of all actions taken in this turn
        execution_log = []

        # Using a context object to track state across the loop (e.g. network_id updates)
        loop_context = {"network_id": network_id, "tools_executed": False}

        while iteration < max_iterations:
            iteration += 1
            
            # Step A: Consume Stream
            # Returns aggregated text and a list of tool calls
            chunk_text, function_calls = await self._consume_stream(current_response, queue)
            
            if chunk_text:
                final_text_content += chunk_text

            # Step B: Check for Completion or Tool Calls
            if not function_calls:
                # No tools called. Check for "Lazy Intent" (Reflection)
                if await self._check_and_handle_lazy_intent(
                    final_text_content, history, loop_context, queue, all_tools, tool_config, session
                ):
                    # Lazy Intent Detected & Alert Added to History.
                    logger.info("Lazy Intent detected. Retrying generation...")
                    current_response = await self._gemini_generate(history, all_tools, tool_config)
                    continue

                # NEW: If tools were executed but we have no meaningful response text, force a summary.
                # We check loop_context to see if we did anything.
                if loop_context.get("tools_executed", False) and not final_text_content.strip():
                    logger.info("Tools executed but no final text. Forcing summary generation.")
                    # We inject a user prompt to force the model to summarize.
                    # Note: history already has the tool outputs appended in previous iterations.
                    summary_request = "The actions have been completed. Please provide a concise final report summarizing what was done (e.g., 'Layout updated', 'Metrics calculated') and any relevant findings."
                    history.append(types.Content(role="user", parts=[types.Part.from_text(text=summary_request)]))
                    
                    # Generate again
                    current_response = await self._gemini_generate(history, all_tools, tool_config)
                    continue
                
                # If we are truly done (no tools, no lazy intent), exit.
                if not final_text_content:
                    return "I have processed your request.", execution_log
                return final_text_content, execution_log

            # Step C: Execute Tools (Parallelized)
            step_log = await self._execute_tools_and_update_history(
                function_calls, chunk_text, history, queue, chat_id, loop_context, session
            )
            execution_log.append(step_log)
            
            # Step D: Next Generation
            logger.info(f"--- Gemini API Request (Iteration {iteration}) ---")
            current_response = await self._gemini_generate(history, all_tools, tool_config)

        if not final_text_content:
            return "I have completed the requested actions, but the process reached its step limit before generating a final report.", execution_log

        return final_text_content, execution_log
    
    # ... (retry decorators omitted, kept as is in original file) ...
    # Note: I am not replacing _gemini_generate or _consume_stream, assuming they are outside the range or handled separately.
    # The tool replacement range ends at 458, which is _handle_side_effects.
    
    # Need to skip down to _execute_tools_and_update_history replacement.
    
    # ...

    async def _execute_tools_and_update_history(
        self,
        function_calls: List[Any],
        text_content: str,
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
        function_calls_parts = []
        function_responses_parts = []
        
        # For the log
        step_record = {
            "step_type": "tool_execution",
            "thought": text_content,
            "tool_calls": []
        }

        if text_content:
            function_calls_parts.append(types.Part.from_text(text=text_content))

        if function_calls:
            loop_context["tools_executed"] = True

        # 1. Prepare Tasks
        tasks = []
        for fc in function_calls:
            function_calls_parts.append(types.Part(function_call=fc))
            feature_name = fc.name
            args = dict(fc.args)

            # Record in log
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
        # Returns list of (result, status, error_msg, feature_name)
        results = await asyncio.gather(*tasks)

        # 3. Process Results (Sequential Side Effects)
        for result, status, error_msg, feature_name in results:
            
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

            # Update log with result (find usage)
            for call_record in step_record["tool_calls"]:
                if call_record["name"] == feature_name and "result" not in call_record:
                    call_record["result"] = result
                    call_record["status"] = status
                    call_record["error"] = error_msg
                    break

        # Update History with valid turn structure
        history.append(types.Content(role="model", parts=function_calls_parts))
        history.append(types.Content(role="user", parts=function_responses_parts))
        
        return step_record

    async def _run_tool_with_events(
        self, feature_name: str, args: Dict[str, Any], chat_id: int, network_id: int, session: Any, queue: Any
    ) -> Tuple[Any, str, Optional[str], str]:
        """
        Wrapper to handle event emission and execution for a single tool.
        Returns (result, status, error_msg, feature_name)
        """
        # Emit "Started" event
        await self._emit_tool_event(queue, feature_name, "started", args)

        # Execute
        result, status, error_msg = await self._run_tool(
            feature_name, args, chat_id, network_id, session
        )
        
        # Emit "Completed" event
        await self._emit_tool_event(queue, feature_name, status, error_msg)
        
        return result, status, error_msg, feature_name

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
            if self.db:
                chat = self.db.query(models.Chat).filter(models.Chat.id == chat_id).first()
                if chat:
                    chat.network_id = new_id
                    if vis_data:
                        chat.visualization_state = vis_data
                    self.db.commit()
            
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
            if self.db:
                chat = self.db.query(models.Chat).filter(models.Chat.id == chat_id).first()
                if chat:
                    chat.visualization_state = vis_data
                    self.db.commit()

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

    async def _emit_tool_event(self, queue: Any, tool: str, status: str, args_or_error: Any):
        data = {"tool": tool, "status": status}
        if status == "started":
            data["args"] = args_or_error
        else:
            data["error"] = args_or_error
        await queue.put({"event": "tool_execution", "data": json.dumps(data)})

    async def _emit_render_update(self, queue: Any, vis_data: Dict):
        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})


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
