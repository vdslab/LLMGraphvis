import json
from typing import Optional

from sqlalchemy.orm import Session

from common import models
from app.core import database
from app.core.logging import get_logger
from app.services import llm as llm_service
from app.services.llm import context as llm_context
from app.services.llm import mcp_client

logger = get_logger(__name__)


async def _handle_background_error(chat_id: int, e: Exception, message: str) -> None:
    logger.exception(f"{message}: {e}")
    queue = await llm_service.get_event_queue(chat_id)
    await queue.put({"event": "training_error" if "training" in message else "error", "data": json.dumps(str(e))})

    # If it's a process error, persist to DB
    if "process" in message:
        # Use a fresh session for error logging
        db_error = database.SessionLocal()
        try:
            error_content = f"I encountered an internal error while processing your request: {str(e)}"
            db_err_msg = models.ChatMessage(
                chat_id=chat_id, role="model", content=error_content
            )
            db_error.add(db_err_msg)
            db_error.commit()

            await queue.put(
                {"event": "message_complete", "data": json.dumps({"id": db_err_msg.id})}
            )
        except Exception as inner_e:
            logger.error(f"Failed to save error message to DB: {inner_e}")
            db_error.rollback()
        finally:
            db_error.close()

async def handle_upload_background(chat_id: int, network_id: int, graphml_data: str) -> None:
    """
    Background task to handle network upload and initialization.
    Executes the initialization steps granularly to provide progress updates.
    """
    logger.info(
        f"Background upload started for chat_id={chat_id}, network_id={network_id}"
    )
    
    queue = await llm_service.get_event_queue(chat_id)
    
    try:
        # Step 1: Import
        thoughts = []
        msg = "Importing GraphML data..."
        thoughts.append(msg)
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": msg + "\n"})})
        
        import_result = await mcp_client.execute_tool(
            "network_import_graphml",
            {"network_id": network_id, "graphml_data": graphml_data},
        )
        
        if "error" in import_result:
            raise ValueError(f"Import failed: {import_result['error']}")
            
        final_network_id = import_result.get("network_id")
        if final_network_id is None:
             raise ValueError("Import tool did not return a valid network_id")

        # Step 2: Layout
        msg = "Calculating ForceAtlas2 layout..."
        thoughts.append(msg)
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": msg + "\n"})})
        
        layout_result = await mcp_client.execute_tool(
            "layout_forceatlas2",
            {"network_id": final_network_id}
        )
        
        # layout tool returns string message or "Error: ..."
        if isinstance(layout_result, str) and layout_result.startswith("Error"):
             raise ValueError(layout_result)

        # Step 3: Visualization
        msg = "Generating initial visualization..."
        thoughts.append(msg)
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": msg + "\n"})})
        
        vis_data = await mcp_client.execute_tool(
            "visualization_generate",
            {"network_id": final_network_id}
        )
        
        # Check if vis_data is an error dict (though tool raises/returns dict usually)
        if isinstance(vis_data, dict) and "error" in vis_data:
             raise ValueError(f"Visualization failed: {vis_data['error']}")

        # Step 4: Inspect the uploaded data (fixed step, not an LLM tool call).
        # Reads the network's structure/attributes directly so the user can see
        # what the data contains before sending their first message.
        msg = "Inspecting uploaded data..."
        thoughts.append(msg)
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": msg + "\n"})})

        data_overview = await llm_context.build_data_overview(final_network_id)

        # Update Chat record with new network_id (if changed) and visualization_state
        # Use a fresh session for this background operation
        db_session = database.SessionLocal()
        try:
            chat = (
                db_session.query(models.Chat)
                .filter(models.Chat.id == chat_id)
                .first()
            )
            if chat:
                # Update network_id if collision occurred
                if final_network_id != network_id:
                     logger.info(
                        f"Network ID updated from {network_id} to {final_network_id} due to collision/re-upload."
                    )
                     chat.network_id = final_network_id
                
                # ALWAYS save the initial visualization state
                if vis_data:
                    chat.visualization_state = vis_data
                    logger.info(f"Saved initial visualization state for chat_id={chat_id}")
                
                # Persist the success message with thoughts, including the data
                # overview so the contents are visible before the first message.
                full_thought = "\n".join(thoughts)
                success_line = "Graph uploaded and initialized successfully."
                if data_overview:
                    final_content = (
                        f"<thought>{full_thought}</thought>\n\n"
                        f"{success_line}\n\n{data_overview}"
                    )
                else:
                    final_content = f"<thought>{full_thought}</thought>\n\n{success_line}"
                
                db_msg = models.ChatMessage(
                    chat_id=chat_id,
                    role="model",
                    content=final_content
                )
                db_session.add(db_msg)
                db_session.commit()
                db_session.refresh(db_msg)
                
                # Broadcast message event (replaces system_message)
                # We send role="assistant" for frontend consistency
                await queue.put({
                    "event": "message",
                    "data": json.dumps({
                        "id": db_msg.id,
                        "role": "assistant",
                        "content": db_msg.content,
                        "created_at": db_msg.created_at.isoformat() if db_msg.created_at else None
                    })
                })

        finally:
            db_session.close()

        # Broadcast render_update
        logger.info(f"Broadcasting render_update for chat_id={chat_id}")
        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})

    except Exception as e:
        await _handle_background_error(chat_id, e, "Error in upload background task")


async def handle_process_background(chat_id: int, user_message: str) -> None:
    """
    Background task to process chat message with LLM.
    Orchestrates the Agent interaction and persists messages.
    """
    logger.info(
        f"Background process started for chat_id={chat_id}, message='{user_message[:50]}...'"
    )
    db = database.SessionLocal()
    try:
        # Process chat and get response
        # process_turn now returns (final_text, execution_log, total_usage, provider_name, model_name)
        (
            final_response_text,
            execution_log,
            total_usage,
            provider_name,
            model_name,
        ) = await llm_service.process_chat(chat_id, user_message, db)

        # Save Assistant Message
        if final_response_text:
            db_msg = models.ChatMessage(
                chat_id=chat_id,
                role="model",
                content=final_response_text,
            )
            db.add(db_msg)
            db.commit()
            db.refresh(db_msg)

            # Persist token usage for this turn, now that db_msg.id exists.
            if total_usage and (total_usage.input_tokens or total_usage.output_tokens):
                from app.services.llm.pricing import estimate_cost_usd

                cost = estimate_cost_usd(
                    model_name,
                    total_usage.input_tokens,
                    total_usage.output_tokens,
                    total_usage.cached_input_tokens,
                    provider=provider_name,
                )
                db.add(models.LlmUsage(
                    message_id=db_msg.id,
                    provider=provider_name,
                    model=model_name,
                    input_tokens=total_usage.input_tokens,
                    output_tokens=total_usage.output_tokens,
                    cached_input_tokens=total_usage.cached_input_tokens,
                    estimated_cost_usd=cost,
                ))
                db.commit()

            # Persist separate Tool Executions
            if execution_log:
                for step in execution_log:
                    if step.get("step_type") == "tool_execution":
                        for tool_call in step.get("tool_calls", []):
                            execution = models.ToolExecution(
                                message_id=db_msg.id,
                                tool_name=tool_call.get("name"),
                                arguments=tool_call.get("args"),
                                result=tool_call.get("result"),
                                thought=step.get("thought"),
                                status=tool_call.get("status", "unknown"),
                                error=tool_call.get("error"),
                                started_at=tool_call.get("started_at"),
                                completed_at=tool_call.get("completed_at")
                            )
                            db.add(execution)
                db.commit()
            
            logger.info(f"Saved assistant message for chat_id={chat_id}")

            # Emit message_complete event
            queue = await llm_service.get_event_queue(chat_id)
            
            # Prepare tool executions for frontend
            tool_executions_data = []
            if execution_log:
                for step in execution_log:
                    if step.get("step_type") == "tool_execution":
                        for tool_call in step.get("tool_calls", []):
                            tool_executions_data.append({
                                "tool_name": tool_call.get("name"),
                                "arguments": tool_call.get("args"),
                                "result": tool_call.get("result"),
                                "thought": step.get("thought"),
                                "status": tool_call.get("status", "unknown"),
                                "error": tool_call.get("error"),
                                "started_at": tool_call.get("started_at").isoformat() if tool_call.get("started_at") else None,
                                "completed_at": tool_call.get("completed_at").isoformat() if tool_call.get("completed_at") else None
                            })

            await queue.put(
                {
                    "event": "message_complete",
                    "data": json.dumps({
                        "id": db_msg.id,
                        "content": db_msg.content,
                        "tool_executions": tool_executions_data
                    })
                }
            )
        else:
            # Even an empty response must emit a terminal event, otherwise the
            # frontend stream stays in the loading state forever.
            logger.warning(f"Empty LLM response for chat_id={chat_id}")
            queue = await llm_service.get_event_queue(chat_id)
            await queue.put(
                {
                    "event": "message_complete",
                    "data": json.dumps({
                        "id": None,
                        "content": None,
                        "tool_executions": []
                    })
                }
            )

    except Exception as e:
        await _handle_background_error(chat_id, e, "Error in process background task")

    finally:
        db.close()
