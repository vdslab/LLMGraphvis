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

            # Handle two-stage centrality workflow
            if tool_name == "calculate_and_store_centrality":
                # Stage 1: Calculate and store centrality
                print(
                    f"Starting Stage 1: Calculate and store {tool_args.get('centrality_type', 'degree')} centrality")

                mcp_payload = {
                    "graphml_content": db_conversation.network.graphml_content if db_conversation.network else create_empty_graphml(),
                    **tool_args
                }

                async with httpx.AsyncClient() as client:
                    url = f"{NETWORKX_MCP_URL}/tools/{tool_name}"
                    print(f"Calling NetworkXMCP: {url} with args {tool_args}")
                    response = await client.post(url, json=mcp_payload, timeout=60.0)

                    if response.status_code == 200:
                        mcp_result = response.json().get("result", {})
                        if mcp_result.get("success"):
                            calculation_id = mcp_result.get("calculation_id")
                            centrality_type = mcp_result.get("centrality_type")

                            print(
                                f"Stage 1 completed. Calculation ID: {calculation_id}")

                            # Stage 2: Automatically call visualization
                            print(
                                f"Starting Stage 2: Generate visualization for calculation {calculation_id}")

                            viz_payload = {
                                "calculation_id": calculation_id,
                                "color_scheme": "viridis",
                                "size_range": [5, 20]
                            }

                            viz_url = f"{NETWORKX_MCP_URL}/tools/get_centrality_visualization"
                            viz_response = await client.post(viz_url, json=viz_payload, timeout=60.0)

                            if viz_response.status_code == 200:
                                viz_result = viz_response.json().get("result", {})
                                if viz_result.get("success"):
                                    # Combine both results for the LLM
                                    combined_result = {
                                        "stage1": mcp_result,
                                        "stage2": viz_result,
                                        "centrality_type": centrality_type,
                                        "calculation_id": calculation_id,
                                        "visualization_data": viz_result.get("visualization_data", {}),
                                        "message": f"Successfully calculated and visualized {centrality_type} centrality"
                                    }
                                    tool_result_content = json.dumps(
                                        {"status": "success", "details": combined_result})
                                else:
                                    tool_result_content = json.dumps({
                                        "status": "partial_success",
                                        "details": {
                                            "stage1": mcp_result,
                                            "stage2_error": viz_result.get("error", "Visualization failed"),
                                            "message": "Calculation completed but visualization failed"
                                        }
                                    })
                            else:
                                tool_result_content = json.dumps({
                                    "status": "partial_success",
                                    "details": {
                                        "stage1": mcp_result,
                                        "stage2_error": f"Visualization request failed with status {viz_response.status_code}",
                                        "message": "Calculation completed but visualization failed"
                                    }
                                })
                        else:
                            tool_result_content = json.dumps({
                                "status": "error",
                                "details": mcp_result.get("error", "Centrality calculation failed")
                            })
                    else:
                        tool_result_content = json.dumps({
                            "status": "error",
                            "details": f"Tool execution failed with status {response.status_code}: {response.text}"
                        })

            elif tool_name == "get_sample_network":
                # Handle sample network generation
                print("Generating sample network for conversation")

                async with httpx.AsyncClient() as client:
                    url = f"{NETWORKX_MCP_URL}/get_sample_network"
                    print(f"Calling NetworkXMCP: {url}")
                    response = await client.get(url, timeout=60.0)

                    if response.status_code == 200:
                        mcp_result = response.json()
                        if mcp_result.get("success"):
                            graphml_content = mcp_result.get("graphml_content")

                            # Update the conversation's network with the sample network
                            if db_conversation.network and graphml_content:
                                try:
                                    db_conversation.network.graphml_content = graphml_content
                                    db.add(db_conversation.network)
                                    db.commit()
                                    db.refresh(db_conversation)
                                    print(
                                        f"Sample network saved to conversation {db_conversation.id}")
                                except Exception as save_error:
                                    print(
                                        f"Warning: failed to save sample network to DB: {save_error}")

                            # Tool result content for LLM
                            tool_result_content = json.dumps({
                                "status": "success",
                                "details": {
                                    "message": "Sample network created successfully",
                                    "metadata": mcp_result.get("metadata", {})
                                }
                            })
                        else:
                            tool_result_content = json.dumps({
                                "status": "error",
                                "details": mcp_result.get("error", "Failed to create sample network")
                            })
                    else:
                        tool_result_content = json.dumps({
                            "status": "error",
                            "details": f"Sample network request failed with status {response.status_code}: {response.text}"
                        })

            else:
                # Handle other tools (existing logic)
                # Prepare payload for NetworkXMCP
                mcp_payload = {
                    "graphml_content": db_conversation.network.graphml_content if db_conversation.network else create_empty_graphml(),
                    **tool_args
                }

                # Call NetworkXMCP
                tool_result_content = ""
                async with httpx.AsyncClient() as client:
                    # If the user requested a layout but the current GraphML is empty, request a sample network first
                    if tool_name in ("calculate_and_store_layout", "change_layout"):
                        graphml_content = mcp_payload.get(
                            "graphml_content", "")
                        if isinstance(graphml_content, str) and "<node" not in graphml_content:
                            try:
                                print(
                                    "No nodes in current GraphML, requesting a sample network from MCP")
                                sample_resp = await client.get(f"{NETWORKX_MCP_URL}/get_sample_network", timeout=60.0)
                                if sample_resp.status_code == 200:
                                    sample_json = sample_resp.json()
                                    sample_graphml = sample_json.get(
                                        "graphml_content")
                                    if sample_graphml:
                                        # Update DB network content so future requests use the sample
                                        try:
                                            db_conversation.network.graphml_content = sample_graphml
                                            db.add(db_conversation.network)
                                            db.commit()
                                            db.refresh(db_conversation)
                                            # Replace payload content
                                            mcp_payload["graphml_content"] = sample_graphml
                                            print(
                                                "Sample network loaded and stored in DB for conversation", db_conversation.id)
                                        except Exception as inner_e:
                                            print(
                                                "Warning: failed to persist sample graphml to DB:", inner_e)
                                else:
                                    print(
                                        "Warning: sample network request returned status", sample_resp.status_code)
                            except Exception as sample_e:
                                print(
                                    "Warning: could not fetch sample network:", sample_e)

                        # Map layout-related tool names to the change_layout endpoint
                        url = f"{NETWORKX_MCP_URL}/tools/change_layout"
                        print(
                            f"Calling MCP change_layout: {url} with args {tool_args}")
                        response = await client.post(url, json=mcp_payload, timeout=60.0)

                        if response.status_code == 200:
                            mcp_result = response.json().get("result", {})
                            if mcp_result.get("success"):
                                # Build network update info for frontend
                                network_update_info = {
                                    "type": "change_layout",
                                    "positions": mcp_result.get("positions", {}),
                                    "graphml_content": mcp_result.get("graphml_content"),
                                    "layout_type": mcp_result.get("layout_type"),
                                    "success": True,
                                }

                                tool_result_content = json.dumps(
                                    {"status": "success", "details": mcp_result})
                            else:
                                tool_result_content = json.dumps(
                                    {"status": "error", "details": mcp_result.get("error", "Unknown error from tool.")})
                        else:
                            tool_result_content = json.dumps(
                                {"status": "error", "details": f"Tool execution failed with status {response.status_code}: {response.text}"})
                    else:
                        url = f"{NETWORKX_MCP_URL}/tools/{tool_name}"
                        print(
                            f"Calling NetworkXMCP: {url} with args {tool_args}")
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
    finally:
        # If we prepared a network_update_info, try broadcasting it via the app's ws_manager
        try:
            if 'network_update_info' in locals() and network_update_info is not None:
                # Import app locally to avoid circular import
                from main import app as main_app
                try:
                    ws_manager = main_app.state.ws_manager
                    await ws_manager.broadcast({
                        "event": "graph_updated",
                        "network_id": network_update_info.get("network_id", conversation_id),
                        "network_update": network_update_info,
                    })
                except Exception as e_b:
                    print(
                        "Warning: failed to broadcast websocket in background task:", e_b)
        except Exception:
            pass


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

            # Handle two-stage centrality workflow
            if tool_name == "calculate_and_store_centrality":
                # Stage 1: Calculate and store centrality
                print(
                    f"Starting Stage 1: Calculate and store {tool_args.get('centrality_type', 'degree')} centrality")

                mcp_payload = {
                    "graphml_content": db_conversation.network.graphml_content if db_conversation.network else create_empty_graphml(),
                    **tool_args
                }

                async with httpx.AsyncClient() as client:
                    url = f"{NETWORKX_MCP_URL}/tools/{tool_name}"
                    print(f"Calling NetworkXMCP: {url} with args {tool_args}")
                    response = await client.post(url, json=mcp_payload, timeout=60.0)

                    if response.status_code == 200:
                        mcp_result = response.json().get("result", {})
                        if mcp_result.get("success"):
                            calculation_id = mcp_result.get("calculation_id")
                            centrality_type = mcp_result.get("centrality_type")

                            print(
                                f"Stage 1 completed. Calculation ID: {calculation_id}")

                            # Stage 2: Automatically call visualization
                            print(
                                f"Starting Stage 2: Generate visualization for calculation {calculation_id}")

                            viz_payload = {
                                "calculation_id": calculation_id,
                                "color_scheme": "viridis",
                                "size_range": [5, 20]
                            }

                            viz_url = f"{NETWORKX_MCP_URL}/tools/get_centrality_visualization"
                            viz_response = await client.post(viz_url, json=viz_payload, timeout=60.0)

                            if viz_response.status_code == 200:
                                viz_result = viz_response.json().get("result", {})
                                if viz_result.get("success"):
                                    # Create networkUpdate for frontend with two-stage data
                                    network_update_info = {
                                        "type": "calculate_and_store_centrality",
                                        "stage1": mcp_result,
                                        "stage2": viz_result,
                                        "centrality_type": centrality_type,
                                        "calculation_id": calculation_id,
                                        "visualization_data": viz_result.get("visualization_data", {}),
                                        "success": True
                                    }

                                    # Tool result for LLM
                                    tool_result_for_llm = {
                                        "status": "success",
                                        "details": {
                                            "stage1": mcp_result,
                                            "stage2": viz_result,
                                            "message": f"Successfully calculated and visualized {centrality_type} centrality"
                                        }
                                    }
                                else:
                                    # Stage 1 success, Stage 2 failed
                                    network_update_info = {
                                        "type": "calculate_and_store_centrality",
                                        "stage1": mcp_result,
                                        "stage2": None,
                                        "centrality_type": centrality_type,
                                        "calculation_id": calculation_id,
                                        "success": False,
                                        "error": "Visualization failed"
                                    }

                                    tool_result_for_llm = {
                                        "status": "partial_success",
                                        "details": {
                                            "stage1": mcp_result,
                                            "stage2_error": viz_result.get("error", "Visualization failed"),
                                            "message": "Calculation completed but visualization failed"
                                        }
                                    }
                            else:
                                # Stage 1 success, Stage 2 request failed
                                network_update_info = {
                                    "type": "calculate_and_store_centrality",
                                    "stage1": mcp_result,
                                    "stage2": None,
                                    "centrality_type": centrality_type,
                                    "calculation_id": calculation_id,
                                    "success": False,
                                    "error": f"Visualization request failed with status {viz_response.status_code}"
                                }

                                tool_result_for_llm = {
                                    "status": "partial_success",
                                    "details": {
                                        "stage1": mcp_result,
                                        "stage2_error": f"Visualization request failed with status {viz_response.status_code}",
                                        "message": "Calculation completed but visualization failed"
                                    }
                                }
                        else:
                            # Stage 1 failed
                            tool_result_for_llm = {
                                "status": "error",
                                "details": mcp_result.get("error", "Centrality calculation failed")
                            }
                    else:
                        # Stage 1 request failed
                        tool_result_for_llm = {
                            "status": "error",
                            "details": f"Tool execution failed with status {response.status_code}: {response.text}"
                        }

            elif tool_name == "get_sample_network":
                # Handle sample network generation
                print("Generating sample network for conversation")

                async with httpx.AsyncClient() as client:
                    url = f"{NETWORKX_MCP_URL}/get_sample_network"
                    print(f"Calling NetworkXMCP: {url}")
                    response = await client.get(url, timeout=60.0)

                    if response.status_code == 200:
                        mcp_result = response.json()
                        if mcp_result.get("success"):
                            graphml_content = mcp_result.get("graphml_content")

                            # Update the conversation's network with the sample network
                            if db_conversation.network and graphml_content:
                                try:
                                    db_conversation.network.graphml_content = graphml_content
                                    db.add(db_conversation.network)
                                    db.commit()
                                    db.refresh(db_conversation)
                                    print(
                                        f"Sample network saved to conversation {db_conversation.id}")
                                except Exception as save_error:
                                    print(
                                        f"Warning: failed to save sample network to DB: {save_error}")

                            # Create network update for frontend
                            network_update_info = {
                                "type": "sample_network_created",
                                "graphml_content": graphml_content,
                                "metadata": mcp_result.get("metadata", {}),
                                "success": True
                            }

                            # Tool result for LLM
                            tool_result_for_llm = {
                                "status": "success",
                                "details": {
                                    "message": "Sample network created successfully",
                                    "metadata": mcp_result.get("metadata", {})
                                }
                            }
                        else:
                            tool_result_for_llm = {
                                "status": "error",
                                "details": mcp_result.get("error", "Failed to create sample network")
                            }
                    else:
                        tool_result_for_llm = {
                            "status": "error",
                            "details": f"Sample network request failed with status {response.status_code}: {response.text}"
                        }

            else:
                # Handle other tools (existing logic)
                mcp_payload = {
                    "graphml_content": db_conversation.network.graphml_content if db_conversation.network else create_empty_graphml(),
                    **tool_args
                }

                tool_result_for_llm = {}
                async with httpx.AsyncClient() as client:
                    # If the user requested a layout but the current GraphML is empty, request a sample network first
                    if tool_name in ("calculate_and_store_layout", "change_layout"):
                        graphml_content = mcp_payload.get(
                            "graphml_content", "")
                        if isinstance(graphml_content, str) and "<node" not in graphml_content:
                            try:
                                print(
                                    "No nodes in current GraphML, requesting a sample network from MCP")
                                sample_resp = await client.get(f"{NETWORKX_MCP_URL}/get_sample_network", timeout=60.0)
                                if sample_resp.status_code == 200:
                                    sample_json = sample_resp.json()
                                    sample_graphml = sample_json.get(
                                        "graphml_content")
                                    if sample_graphml:
                                        try:
                                            db_conversation.network.graphml_content = sample_graphml
                                            db.add(db_conversation.network)
                                            db.commit()
                                            db.refresh(db_conversation)
                                            mcp_payload["graphml_content"] = sample_graphml
                                            print(
                                                "Sample network loaded and stored in DB for conversation", db_conversation.id)
                                        except Exception as inner_e:
                                            print(
                                                "Warning: failed to persist sample graphml to DB:", inner_e)
                                else:
                                    print(
                                        "Warning: sample network request returned status", sample_resp.status_code)
                            except Exception as sample_e:
                                print(
                                    "Warning: could not fetch sample network:", sample_e)

                        # Map layout-related tool names to the change_layout endpoint
                        url = f"{NETWORKX_MCP_URL}/tools/change_layout"
                        print(
                            f"Calling MCP change_layout: {url} with args: {tool_args}")
                        response = await client.post(url, json=mcp_payload, timeout=60.0)

                        if response.status_code == 200:
                            mcp_result = response.json().get("result", {})
                            tool_result_for_llm = {
                                "status": "success", "details": mcp_result}
                            if mcp_result.get("success"):
                                network_update_info = {
                                    "type": "change_layout",
                                    "positions": mcp_result.get("positions", {}),
                                    "graphml_content": mcp_result.get("graphml_content"),
                                    "layout_type": mcp_result.get("layout_type"),
                                    "success": True,
                                }
                        else:
                            error_detail = response.text
                            tool_result_for_llm = {
                                "status": "error", "details": f"Tool execution failed with status {response.status_code}: {error_detail}"}
                    else:
                        url = f"{NETWORKX_MCP_URL}/tools/{tool_name}"
                        print(
                            f"Calling MCP Tool: {url} with args: {tool_args}")
                        response = await client.post(url, json=mcp_payload, timeout=60.0)

                        if response.status_code == 200:
                            mcp_result = response.json().get("result", {})
                            tool_result_for_llm = {
                                "status": "success", "details": mcp_result}
                            if mcp_result.get("success"):
                                network_update_info = {
                                    "type": tool_name, **mcp_result}
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
        # Broadcast network update via WebSocket if present
        try:
            if network_update_info is not None:
                ws_manager = request.app.state.ws_manager
                await ws_manager.broadcast({
                    "event": "graph_updated",
                    "network_id": network_update_info.get("network_id", db_conversation.id),
                    "network_update": network_update_info,
                })
        except Exception as bcast_e:
            print("Warning: failed to broadcast websocket update:", bcast_e)

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
