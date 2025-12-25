import json
import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google import genai
from google.genai import types

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

    async def process_turn(
        self,
        history: List[types.Content],
        queue: Any,
        chat_id: int,
        network_id: int,
        tool_config: Optional[types.ToolConfig] = None,
    ) -> str:
        """
        Orchestrates a single turn of the agent (User Input -> [Thoughts/Actions] -> Final Response).
        """
        logger.info(f"Starting agent turn for Chat ID: {chat_id}, Network ID: {network_id}")
        
        # 1. Prepare Tools
        all_tools = await self._get_all_tools()

        # 2. Generate Initial Response Stream
        try:
            current_response = await self.client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=all_tools,
                    tool_config=tool_config,
                    temperature=0.1,
                ),
            )
        except Exception as e:
            logger.error(f"Initial generation failed: {e}")
            raise e

        # 3. Enter Tool Execution Loop
        return await self._execute_tool_loop(
            initial_response=current_response,
            history=history,
            all_tools=all_tools,
            tool_config=tool_config,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
        )

    async def _execute_tool_loop(
        self,
        initial_response: Any,
        history: List[types.Content],
        all_tools: List[types.Tool],
        tool_config: Optional[types.ToolConfig],
        queue: Any,
        chat_id: int,
        network_id: int,
    ) -> str:
        """
        Manages the ReAct loop: Consumption -> Execution -> Observation -> Next Generation.
        """
        current_response = initial_response
        max_iterations = 10
        iteration = 0
        final_text_content = ""

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
                    final_text_content, history, loop_context, queue, all_tools, tool_config
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
                    return "I have processed your request."
                return final_text_content

            # Step C: Execute Tools (if any)
            await self._execute_tools_and_update_history(
                function_calls, chunk_text, history, queue, chat_id, loop_context
            )
            
            # Step D: Next Generation
            logger.info(f"--- Gemini API Request (Iteration {iteration}) ---")
            current_response = await self._gemini_generate(history, all_tools, tool_config)

        return final_text_content

    async def _gemini_generate(self, history, tools, tool_config):
        try:
            return await self.client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tools,
                    tool_config=tool_config,
                    temperature=0.1,
                ),
            )
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise e

    async def _consume_stream(self, response: Any, queue: Any) -> Tuple[str, List[Any]]:
        """Consumes stream, emits chunks to UI, and collects tool calls."""
        final_text = ""
        all_function_calls = []

        if hasattr(response, "__aiter__"):  # Stream
            try:
                async for chunk in response:
                    if chunk.candidates:
                        candidate = chunk.candidates[0]
                        for part in candidate.content.parts:
                            if part.text:
                                final_text += part.text
                                await self._emit_message_chunk(queue, part.text)
                            if part.function_call:
                                all_function_calls.append(part.function_call)
            except Exception as e:
                logger.error(f"Stream consumption error: {e}")
                logger.error(traceback.format_exc())
                raise e
        else:
            # Static response
            if response.candidates:
                content = response.candidates[0].content
                for part in content.parts:
                    if part.text:
                        final_text += part.text
                        await self._emit_message_chunk(queue, part.text)
                    if part.function_call:
                        all_function_calls.append(part.function_call)

        return final_text, all_function_calls

    async def _check_and_handle_lazy_intent(
        self,
        text_content: str,
        history: List[types.Content],
        loop_context: Dict[str, Any],
        queue: Any,
        all_tools: List[types.Tool],
        tool_config: Optional[types.ToolConfig],
    ) -> bool:
        """
        Uses a lightweight LLM call (Reflection) to detect if the model promised an action but didn't call a tool.
        Returns True if a system alert was added to history (signaling a need to retry).
        """
        # 1. Quick heuristic check to avoid wasting LLM calls on short/empty texts
        if len(text_content) < 10:
            return False

        # 2. Check recent history to prevent infinite loops
        retry_count = 0
        if hasattr(history, '__iter__'):
             range_check = history[-2:] if len(history) >= 2 else history
             for part in range_check:
                 # Check 'parts' of the content
                 if hasattr(part, 'parts'):
                     for p in part.parts:
                         if p.text and "SYSTEM_ALERT" in p.text:
                             retry_count += 1
        
        if retry_count >= 2:
            return False

        # 3. Reflection: Is this lazy?
        is_lazy = await self._is_lazy_response(text_content)
        
        if is_lazy:
            logger.warning(f"Lazy Intent Detected via Reflection: '{text_content[:50]}...'")
            
            # The model's last turn (text_content) is not yet in history?
            # 'history' passed here matches what was sent to the model for the *previous* generation.
            # The *current* response (text_content) is what we just consumed.
            # Use standard convention: Append Model's Text -> Append User's Alert.
            
            history.append(types.Content(role="model", parts=[types.Part.from_text(text=text_content)]))
            
            alert_msg = (
                "SYSTEM_ALERT: You stated an intent to act (e.g., 'I will analyze'), but issued NO tool calls. "
                "Do not plan. EXECUTE the tool call immediately. "
                "Call the appropriate tool definition NOW."
            )
            history.append(types.Content(role="user", parts=[types.Part.from_text(text=alert_msg)]))
            
            # Since we manually added the model's text response to history here to "save" it,
            # we don't want the outer loop to add it again. 
            # However, the outer loop logic (in _execute_tools_and_update_history) usually adds it.
            # But we are RETURNING True here, and the caller handles the retry loop.
            return True

        return False

    async def _is_lazy_response(self, text: str) -> bool:
        """
        Ask the model (self-reflection) if the text indicates a missed action.
        """
        try:
            # Using a simplified prompt for speed/cost
            prompt = f"""
            Analyze the following AI response. 
            Does it promise to perform an action (e.g., 'I will now calculate', 'Checking...', 'Let's visualize') WITHOUT actually providing a result?
            Refuse to flag it if it's just a greeting, a question to the user, or a completion report.
            
            Text: "{text}"
            
            Answer YES or NO.
            """
            
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            
            result = response.text.upper() if response.text else ""
            return "YES" in result
        except Exception as e:
            logger.warning(f"Reflection check failed: {e}")
            return False

    async def _execute_tools_and_update_history(
        self,
        function_calls: List[Any],
        text_content: str,
        history: List[types.Content],
        queue: Any,
        chat_id: int,
        loop_context: Dict[str, Any],
    ):
        """Executes tools in parallel/sequence and updates history."""
        function_calls_parts = []
        function_responses_parts = []
        
        if text_content:
            function_calls_parts.append(types.Part.from_text(text=text_content))

        if function_calls:
            loop_context["tools_executed"] = True

        for fc in function_calls:
            function_calls_parts.append(types.Part(function_call=fc))
            feature_name = fc.name
            args = dict(fc.args)

            # Emit "Started" event
            await self._emit_tool_event(queue, feature_name, "started", args)

            # Execute
            result, status, error_msg = await self._run_tool(
                feature_name, args, chat_id, loop_context["network_id"]
            )

            # Handle Side Effects (Visualization, Context Switch)
            if status == "completed":
                # Updates network_id in loop_context if changed
                await self._handle_side_effects(
                    feature_name, result, chat_id, queue, loop_context
                )

            # Emit "Completed" event
            await self._emit_tool_event(queue, feature_name, status, error_msg)

            # Collect Response
            function_responses_parts.append(
                types.Part.from_function_response(name=feature_name, response=result)
            )

        # Update History with valid turn structure
        history.append(types.Content(role="model", parts=function_calls_parts))
        history.append(types.Content(role="user", parts=function_responses_parts))

    async def _run_tool(
        self, function_name: str, args: Dict[str, Any], chat_id: int, network_id: int
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
                result = await mcp_client.execute_tool(function_name, args)
            
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
    ):
        """Handles Visualization updates and Network ID switching."""
        if not isinstance(result, dict):
            return

        current_network_id = loop_context["network_id"]

        # 1. Context Switching
        if "new_network_id" in result and result["new_network_id"] != current_network_id:
            new_id = result["new_network_id"]
            logger.info(f"Context switch: {current_network_id} -> {new_id}")
            
            # Update DB (omitted specific DB logic for brevity, assuming service layer handles it or simple update)
            if self.db:
                chat = self.db.query(models.Chat).filter(models.Chat.id == chat_id).first()
                if chat:
                    chat.network_id = new_id
                    self.db.commit()
            
            # Update Loop Context
            loop_context["network_id"] = new_id
            
            # Auto-Visualize
            await self._auto_generate_visualization(new_id, queue)
            return

        # 2. Visualization Updates
        vis_data = None
        if function_name == "generate_visualization":
            vis_data = result
        elif function_name == "initialize_network" and "network" in result:
            vis_data = result["network"]

        if vis_data and "nodes" in vis_data:
            await self._emit_render_update(queue, vis_data)
            # Save state
            if self.db:
                chat = self.db.query(models.Chat).filter(models.Chat.id == chat_id).first()
                if chat:
                    chat.visualization_state = vis_data
                    self.db.commit()

    async def _auto_generate_visualization(self, network_id: int, queue: Any):
        """Triggers visualization generation for a new network context."""
        try:
            vis_data = await mcp_client.execute_tool(
                "generate_visualization", {"network_id": network_id}
            )
            if isinstance(vis_data, dict) and "nodes" in vis_data:
                await self._emit_render_update(queue, vis_data)
        except Exception as e:
            logger.error(f"Auto-vis failed for {network_id}: {e}")

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
    
    return await agent._execute_tool_loop(
        initial_response=initial_response,
        history=history,
        all_tools=all_tools,
        tool_config=tool_config,
        queue=queue,
        chat_id=chat_id,
        network_id=network_id
    )
