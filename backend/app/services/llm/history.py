from typing import List
from sqlalchemy.orm import Session
from google.genai import types
from app import models

def build_history(chat_id: int, user_message: str, db: Session) -> List[types.Content]:
    """Build conversation history with few-shot examples."""
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.chat_id == chat_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    history = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))
    
    # Check if the last message in history is the same as the user_message
    # This prevents duplication if the message was already saved to DB and fetched
    if not history or history[-1].parts[0].text != user_message:
        history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    
    # Few-shot examples
    example_1 = [
        types.Content(role="user", parts=[types.Part(text="Show popular nodes")]),
        types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="list_node_attributes", args={}))]),
        types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="list_node_attributes", response={"attributes": ["weight"]}))]),
        types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="calculate_centrality", args={"centrality_type": "degree"}))]),
        types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="calculate_centrality", response={"status": "success", "message": "Calculated degree centrality."}))]),
        types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="list_node_attributes", args={}))]),
        types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="list_node_attributes", response={"attributes": ["weight", "degree_centrality"]}))]),
        types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="generate_visualization", args={"layout_name": "spring", "node_size_config": {"attribute": "degree_centrality", "min": 5, "max": 50}}))]),
        types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="generate_visualization", response={"status": "success", "message": "Visualization created."}))])
    ]
    
    return example_1 + history
