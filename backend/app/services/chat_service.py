import json
from typing import Optional

from sqlalchemy.orm import Session

from common import models
from app.core import database
from app.core.logging import get_logger
from app.services import llm as llm_service
from app.services.llm import context as llm_context
from app.services.llm import emitters
from app.services.llm import markup
from app.services.llm import mcp_client
from app.services.llm import titles

logger = get_logger(__name__)


async def _apply_chat_name(db: Session, chat: models.Chat, name: str) -> None:
    """Persist an auto-generated chat name and tell the open UI about it.

    Only ever called for chats the user has not renamed themselves — the
    `name_is_custom` check belongs to the caller, which already holds the row.
    """
    chat.name = name
    db.commit()

    queue = await llm_service.get_event_queue(chat.id)
    await queue.put(
        {
            "event": "chat_renamed",
            "data": json.dumps({"chat_id": chat.id, "name": name}),
        }
    )
    logger.info(f"Auto-named chat {chat.id}: {name!r}")


async def _maybe_autoname_chat(
    db: Session,
    chat_id: int,
    user_message: str,
    assistant_message: str,
    provider_name: str,
    model_name: str,
) -> None:
    """Title the chat from its first exchange.

    Runs at most once per chat — it requires the chat to still have exactly one
    user message — and never touches a chat the user has renamed. Any failure is
    logged and dropped: the turn itself has already succeeded.
    """
    try:
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat or chat.name_is_custom:
            return

        user_message_count = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.chat_id == chat_id,
                models.ChatMessage.role == "user",
            )
            .count()
        )
        if user_message_count != 1:
            return

        title = await titles.generate_chat_title(
            user_message=user_message,
            assistant_message=assistant_message,
            provider_name=provider_name or None,
            model_name=model_name or None,
            current_name=chat.name,
        )
        if title and title != chat.name:
            await _apply_chat_name(db, chat, title)
    except Exception as e:
        logger.warning(f"Failed to auto-name chat {chat_id}: {e}")


def _name_network_after_file(network_id: int, filename: Optional[str]) -> None:
    """Replace a network's placeholder name with one taken from the upload.

    A network is created as "<chat name> Network" before anything is uploaded
    to it, so an untouched chat leaves it called "New Chat Network" — a name
    that then reads, in the overview and in the agent's context, as though it
    were the graph's own. Only that placeholder shape is overwritten.
    """
    file_name = titles.name_from_filename(filename)
    if not file_name:
        return

    db = database.SessionLocal()
    try:
        network = (
            db.query(models.Network).filter(models.Network.id == network_id).first()
        )
        if not network:
            return
        current = (network.name or "").removesuffix(" Network")
        if not titles.is_placeholder_name(current):
            return
        network.name = file_name
        db.commit()
        logger.info(f"Named network {network_id} after the upload: {file_name!r}")
    except Exception as e:
        logger.warning(f"Could not name network {network_id}: {e}")
        db.rollback()
    finally:
        db.close()


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

async def handle_upload_background(
    chat_id: int,
    network_id: int,
    graphml_data: str,
    filename: Optional[str] = None,
) -> None:
    """
    Background task to handle network upload and initialization.
    Executes the initialization steps granularly to provide progress updates.
    """
    logger.info(
        f"Background upload started for chat_id={chat_id}, network_id={network_id}"
    )
    
    queue = await llm_service.get_event_queue(chat_id)

    # Fixed pipeline steps, reported as `progress` events rather than
    # `thinking_stream`: no model reasoning happens during an upload, and
    # labelling these as the agent's thoughts is simply untrue.
    steps: list[str] = []

    async def step(label: str) -> None:
        steps.append(label)
        await emitters.emit_progress(queue, label, status="running")

    try:
        # Step 1: Import
        await step("Importing GraphML data")

        import_result = await mcp_client.execute_tool(
            "network_import_graphml",
            {"network_id": network_id, "graphml_data": graphml_data},
        )
        
        if "error" in import_result:
            raise ValueError(f"Import failed: {import_result['error']}")
            
        final_network_id = import_result.get("network_id")
        if final_network_id is None:
             raise ValueError("Import tool did not return a valid network_id")

        # Before the overview is built, so it reports the file's name and not
        # the placeholder the network was created with.
        _name_network_after_file(final_network_id, filename)

        # Step 2: Layout
        await step("Calculating ForceAtlas2 layout")

        layout_result = await mcp_client.execute_tool(
            "layout_forceatlas2",
            {"network_id": final_network_id}
        )
        
        # layout tool returns string message or "Error: ..."
        if isinstance(layout_result, str) and layout_result.startswith("Error"):
             raise ValueError(layout_result)

        # Step 3: Visualization
        await step("Generating initial visualization")

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
        await step("Inspecting uploaded data")

        overview_title, data_overview = await llm_context.build_data_overview(
            final_network_id
        )

        await emitters.emit_progress(queue, steps[-1], status="done")

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

                # Provisional name from the uploaded file, so the chat stops
                # being "New Chat" before the first message is even sent. The
                # LLM title generated after the first exchange supersedes it.
                renamed_to = None
                if not chat.name_is_custom and titles.is_placeholder_name(chat.name):
                    file_name = titles.name_from_filename(filename)
                    if file_name:
                        chat.name = file_name
                        renamed_to = file_name

                # Persist the success message with the step log, plus the data
                # overview folded behind a one-line summary so the contents are
                # available before the first message without filling the panel.
                parts = [
                    markup.steps_block(steps),
                    "Graph uploaded and initialized successfully.",
                ]
                if data_overview:
                    parts.append(markup.collapsible(overview_title, data_overview))
                final_content = "\n\n".join(part for part in parts if part)

                db_msg = models.ChatMessage(
                    chat_id=chat_id,
                    role="model",
                    content=final_content
                )
                db_session.add(db_msg)
                db_session.commit()
                db_session.refresh(db_msg)
                
                if renamed_to:
                    logger.info(f"Named chat {chat_id} after upload: {renamed_to!r}")
                    await queue.put({
                        "event": "chat_renamed",
                        "data": json.dumps({"chat_id": chat_id, "name": renamed_to}),
                    })

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

            # Name the chat from what it turned out to be about. Runs after the
            # turn is already reported as complete, so a slow or failing title
            # call cannot delay the answer.
            await _maybe_autoname_chat(
                db, chat_id, user_message, final_response_text, provider_name, model_name
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
