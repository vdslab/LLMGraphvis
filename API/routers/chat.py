"""
Chat router for the API.
Handles conversations, messages, and orchestrates interactions with the LLM and NetworkXMCP.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
import datetime
import httpx
import os
import networkx as nx
import io

import models
import schemas
import auth
from database import get_db
from services.llm import process_chat_message
from services.rate_limiter import limiter

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={401: {"description": "Unauthorized"}},
)

# NetworkXMCPサーバーとの通信はproxy.pyを介して行う
# APIサーバー内部では直接NetworkXMCPサーバーにアクセス
NETWORKX_MCP_URL = os.environ.get(
    "NETWORKX_MCP_URL", "http://networkx-mcp:8001")


def create_empty_graphml() -> str:
    """Creates an empty GraphML string."""
    G = nx.Graph()
    output = io.BytesIO()
    nx.write_graphml(G, output)
    return output.getvalue().decode('utf-8')


@router.post("/conversations", response_model=schemas.Conversation)
async def create_conversation(
    conversation: schemas.ConversationCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new conversation and an associated empty network.
    """
    db_conversation = models.Conversation(
        title=conversation.title,
        user_id=current_user.id
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)

    # Create an associated empty network
    db_network = models.Network(
        name="Initial Network",
        conversation_id=db_conversation.id,
        graphml_content=create_empty_graphml()
    )
    db.add(db_network)
    db.commit()
    db.refresh(db_conversation)  # Refresh to load the network relationship

    return db_conversation


@router.get("/conversations", response_model=List[schemas.Conversation])
async def get_conversations(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all conversations for the current user.
    """
    return db.query(models.Conversation).filter(models.Conversation.user_id == current_user.id).all()


@router.get("/conversations/{conversation_id}", response_model=schemas.Conversation)
async def get_conversation(
    conversation_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific conversation by ID.
    """
    db_conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()

    if db_conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return db_conversation


@router.get("/conversations/{conversation_id}/messages", response_model=List[schemas.ChatMessage])
async def get_messages(
    conversation_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all messages for a conversation.
    """
    # Check if conversation exists and belongs to user
    db_conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()

    if db_conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return db.query(models.ChatMessage).filter(
        models.ChatMessage.conversation_id == conversation_id
    ).order_by(models.ChatMessage.created_at).all()


@router.post("/conversations/{conversation_id}/messages", response_model=schemas.ChatMessage)
@limiter.limit("100/hour")  # Use configured rate limit
async def create_message(
    conversation_id: int,
    message: schemas.ChatMessageCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new message, process it with the LLM, and potentially trigger network operations.
    """
    db_conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()

    if db_conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # メッセージが辞書型の場合は文字列に変換
    message_content = message.content
    if isinstance(message_content, dict):
        message_content = json.dumps(message_content)

    # Save user message
    db_message = models.ChatMessage(
        content=message_content,
        role="user",
        user_id=current_user.id,
        conversation_id=conversation_id
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    # Process message in the background
    background_tasks.add_task(
        process_and_respond,
        db=db,
        conversation_id=conversation_id,
        user_message_content=message.content
    )

    return db_message


async def process_and_respond(db: Session, conversation_id: int, user_message_content):
    """
    Process user message, interact with LLM and NetworkXMCP, and save the response.
    This version handles the full conversation loop including tool calls and feedback.
    """
    # メッセージが辞書型の場合は文字列に変換
    if isinstance(user_message_content, dict):
        user_message_content = json.dumps(user_message_content)
    # メッセージが文字列でない場合も文字列に変換する
    elif not isinstance(user_message_content, str):
        user_message_content = str(user_message_content)

    db_conversation = db.query(models.Conversation).get(conversation_id)
    if not db_conversation:
        print(f"Error: Conversation with ID {conversation_id} not found.")
        return

    try:
        # 1. Get conversation history
        history = db.query(models.ChatMessage).filter(
            models.ChatMessage.conversation_id == conversation_id
        ).order_by(models.ChatMessage.created_at).all()
        formatted_history = [
            {"role": msg.role, "content": msg.content} for msg in history]

        # 2. Call LLM to get the next step (either a tool call or a direct response)
        llm_response = await process_chat_message(formatted_history)

        tool_calls = llm_response.get("tool_calls")

        if tool_calls:
            # 3. Execute the tool call
            tool_call = tool_calls[0]  # Assuming one tool call for now
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]  # Already a dict

            # Prepare payload for NetworkXMCP
            mcp_payload = {
                "graphml_content": db_conversation.network.graphml_content if db_conversation.network else create_empty_graphml(),
                **tool_args
            }

            # Call NetworkXMCP
            tool_result_content = ""
            async with httpx.AsyncClient() as client:
                url = f"{NETWORKX_MCP_URL}/tools/{tool_name}"
                print(f"Calling NetworkXMCP: {url} with args {tool_args}")
                response = await client.post(url, json=mcp_payload, timeout=60.0)

                if response.status_code == 200:
                    mcp_result = response.json().get("result", {})
                    if mcp_result.get("success"):
                        # Update network or handle data
                        # This part needs to be robust
                        if 'positions' in mcp_result:
                            # ... (update graphml with new positions)
                            pass
                        if 'centrality_values' in mcp_result:
                            # The result is the centrality data itself.
                            # We'll pass this back to the LLM to summarize.
                            pass

                        # Create a summary of the successful tool result for the LLM
                        tool_result_content = json.dumps(
                            {"status": "success", "details": mcp_result})
                    else:
                        tool_result_content = json.dumps(
                            {"status": "error", "details": mcp_result.get("error", "Unknown error from tool.")})
                else:
                    tool_result_content = json.dumps(
                        {"status": "error", "details": f"Tool execution failed with status {response.status_code}: {response.text}"})

            # 4. Send the tool result back to the LLM to get a natural language response
            # Append the original llm_response (with the tool call) and the tool result to the history
            formatted_history.append(
                {"role": "assistant", "content": json.dumps(llm_response)})
            formatted_history.append(
                {"role": "tool", "content": tool_result_content})

            final_llm_response = await process_chat_message(formatted_history)
            assistant_content = final_llm_response.get(
                "content", "I've completed the operation.")

        else:
            # No tool call, just a direct response from the LLM
            assistant_content = llm_response.get(
                "content", "I'm not sure how to respond to that.")

        # 5. Save the final assistant response
        db_response = models.ChatMessage(
            content=assistant_content,
            role="assistant",
            user_id=db_conversation.user_id,
            conversation_id=conversation_id,
            # Store the initial LLM response for debugging
            meta_data=json.dumps(llm_response)
        )
        db.add(db_response)
        db.commit()

    except Exception as e:
        print(f"Error in process_and_respond: {str(e)}")
        # Log and save error message
        error_content = f"An error occurred: {str(e)}"
        db_error = models.ChatMessage(
            content=error_content,
            role="assistant",
            user_id=db_conversation.user_id,
            conversation_id=conversation_id,
            meta_data=json.dumps({"error": True})
        )
        db.add(db_error)
        db.commit()


@router.post("/recommend-layout")
async def recommend_layout(
    request: Request,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Recommend a layout algorithm based on network description and visualization purpose.
    Uses LLM to analyze the requirements and suggest the best layout.
    """
    try:
        body = await request.json()
        description = body.get("description", "")
        purpose = body.get("purpose", "")

        if not description or not purpose:
            raise HTTPException(
                status_code=400, detail="Both description and purpose are required")

        # Create a prompt for the LLM to recommend a layout
        prompt = f"""Based on the following network description and visualization purpose, recommend the most suitable graph layout algorithm.

Network Description: {description}

Visualization Purpose: {purpose}

Available layout algorithms:
- spring: Force-directed layout, good for general networks, shows clustering
- circular: Nodes arranged in a circle, good for showing cycles
- kamada_kawai: Force-directed with better aesthetics, good for small to medium networks
- fruchterman_reingold: Force-directed variant, good for general networks
- spectral: Uses graph spectrum, good for finding communities
- shell: Concentric circles, good for hierarchical or layered networks
- spiral: Spiral arrangement, good for sequential data
- planar: Planar graph layout, good for planar networks
- grid: Grid arrangement, good for regular structures
- tree: Hierarchical tree layout, good for tree-like structures
- radial: Radial layout from center, good for hub-spoke networks
- multipartite: Multi-layer layout, good for multi-partite graphs
- bipartite: Two-layer layout, good for bipartite graphs
- random: Random placement, baseline comparison

Please respond with a JSON object containing:
1. "recommended_layout": the name of the recommended layout (one of the above)
2. "explanation": a brief explanation of why this layout is suitable
3. "recommended_parameters": optional parameters for the layout (can be empty object)

Example response:
{{
  "recommended_layout": "spring",
  "explanation": "Spring layout is ideal for this network because it naturally reveals community structures and highlights hub nodes through force-directed positioning.",
  "recommended_parameters": {{"iterations": 50, "k": 0.1}}
}}

Respond ONLY with the JSON object, no additional text."""

        # Call LLM service
        from services.llm import process_chat_message
        messages = [{"role": "user", "content": prompt}]
        llm_response = await process_chat_message(messages)

        # Parse LLM response
        content = llm_response.get("content", "")

        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            recommendation = json.loads(json_match.group())
        else:
            # Fallback to default recommendation
            recommendation = {
                "recommended_layout": "spring",
                "explanation": "Spring layout is a good default choice for most networks.",
                "recommended_parameters": {}
            }

        return {
            "success": True,
            "recommended_layout": recommendation.get("recommended_layout", "spring"),
            "explanation": recommendation.get("explanation", ""),
            "recommended_parameters": recommendation.get("recommended_parameters", {})
        }

    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response as JSON: {e}")
        # Return a default recommendation
        return {
            "success": True,
            "recommended_layout": "spring",
            "explanation": "Spring layout is recommended as a versatile default for most network types.",
            "recommended_parameters": {}
        }
    except Exception as e:
        print(f"Error in /recommend-layout endpoint: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}")


@router.post("/process")
@limiter.limit("100/hour")  # Use configured rate limit
async def process_chat(
    request: Request,
    response: Response,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Process a chat message from the frontend, handling the full conversation loop.
    This endpoint is the primary interaction point for the chat UI.
    """
    try:
        body = await request.json()
        message_content = body.get("message", "")
        # Allow specifying conversation
        conversation_id = body.get("conversation_id")

        # メッセージが辞書型の場合は文字列に変換
        if isinstance(message_content, dict):
            message_content = json.dumps(message_content)
        # メッセージが文字列でない場合も文字列に変換する
        elif not isinstance(message_content, str):
            message_content = str(message_content)

        if not message_content:
            raise HTTPException(status_code=400, detail="Message is required")

        # Find or create a conversation
        if conversation_id:
            db_conversation = db.query(models.Conversation).filter(
                models.Conversation.id == conversation_id,
                models.Conversation.user_id == current_user.id
            ).first()
            if not db_conversation:
                raise HTTPException(
                    status_code=404, detail="Conversation not found")
        else:
            db_conversation = db.query(models.Conversation).filter(
                models.Conversation.user_id == current_user.id
            ).order_by(models.Conversation.created_at.desc()).first()
            if not db_conversation:
                db_conversation = models.Conversation(
                    title="New Conversation", user_id=current_user.id)
                db.add(db_conversation)
                db.commit()
                db.refresh(db_conversation)
                # Create an associated empty network
                db_network = models.Network(
                    name="Initial Network",
                    conversation_id=db_conversation.id,
                    graphml_content=create_empty_graphml()
                )
                db.add(db_network)
                db.commit()
                db.refresh(db_conversation)

        # Save user message
        db_message = models.ChatMessage(
            content=message_content,
            role="user",
            user_id=current_user.id,
            conversation_id=db_conversation.id
        )
        db.add(db_message)
        db.commit()

        # --- Start Conversation Loop ---

        # 1. Get history
        history = db.query(models.ChatMessage).filter(
            models.ChatMessage.conversation_id == db_conversation.id
        ).order_by(models.ChatMessage.created_at).all()
        formatted_history = [
            {"role": msg.role, "content": msg.content} for msg in history]

        # 2. Call LLM
        llm_response = await process_chat_message(formatted_history)
        tool_calls = llm_response.get("tool_calls")

        final_assistant_content = ""
        network_update_info = None

        if tool_calls:
            # 3. Execute Tool
            tool_call = tool_calls[0]
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]

            mcp_payload = {
                "graphml_content": db_conversation.network.graphml_content if db_conversation.network else create_empty_graphml(),
                **tool_args
            }

            tool_result_for_llm = {}
            async with httpx.AsyncClient() as client:
                url = f"{NETWORKX_MCP_URL}/tools/{tool_name}"
                print(f"Calling MCP Tool: {url} with args: {tool_args}")
                response = await client.post(url, json=mcp_payload, timeout=60.0)

                if response.status_code == 200:
                    mcp_result = response.json().get("result", {})
                    tool_result_for_llm = {
                        "status": "success", "details": mcp_result}
                    if mcp_result.get("success"):
                        network_update_info = {"type": tool_name, **mcp_result}
                        # Potentially update graphml in DB here if needed
                else:
                    error_detail = response.text
                    tool_result_for_llm = {
                        "status": "error", "details": f"Tool execution failed with status {response.status_code}: {error_detail}"}

            # 4. Send tool result back to LLM
            # We need to reconstruct the history for the final summarization call
            final_history = formatted_history + [
                {"role": "assistant", "content": json.dumps(
                    {"tool_calls": tool_calls})},
                {"role": "tool", "content": json.dumps(tool_result_for_llm)}
            ]

            final_response_from_llm = await process_chat_message(final_history)
            final_assistant_content = final_response_from_llm.get(
                "content", "I have completed the requested action.")

        else:
            # No tool call, just a direct response
            final_assistant_content = llm_response.get(
                "content", "I'm not sure how to respond.")

        # 5. Save final assistant response
        db_response = models.ChatMessage(
            content=final_assistant_content,
            role="assistant",
            user_id=current_user.id,
            conversation_id=db_conversation.id,
            # Store initial response for debug
            meta_data=json.dumps(llm_response)
        )
        db.add(db_response)
        db.commit()

        # 6. Return result to frontend
        return {
            "success": True,
            "content": final_assistant_content,
            "conversation_id": db_conversation.id,
            "networkUpdate": network_update_info
        }

    except Exception as e:
        print(f"Error in /process endpoint: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "content": f"An unexpected error occurred: {str(e)}"}
