from typing import List

from google.genai import types
from sqlalchemy.orm import Session

from common import models


def build_history(chat_id: int, user_message: str, db: Session) -> List[types.Content]:
    """Build conversation history with few-shot examples."""
    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.chat_id == chat_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )

    history = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"
        
        # 1. Expand intermediate tool steps from ToolExecution table (New Schema)
        if msg.role == "model" and getattr(msg, "tool_executions", None):
            try:
                # Group executions by thought to reconstruct "steps"
                # Sort by ID to ensure chronological order
                executions = sorted(msg.tool_executions, key=lambda x: x.id)
                
                steps = []
                current_step = None
                
                for exc in executions:
                    # Start a new step if thought changes (or first item)
                    # Note: We treat None thought and "" thought as same for grouping if we want, 
                    # but usually thought is unique per step.
                    if current_step is None or exc.thought != current_step['thought']:
                        if current_step:
                            steps.append(current_step)
                        current_step = {'thought': exc.thought, 'tool_calls': []}
                    
                    current_step['tool_calls'].append(exc)
                
                if current_step:
                    steps.append(current_step)
                
                # Reconstruct history from steps
                for step in steps:
                    # A. Reconstruct Model Turn
                    model_parts = []
                    # Optimization: Do NOT include past "thoughts" in the history.
                    # This prevents the model from looping on its own past planning statements ("I will...")
                    # and encourages "Action First" behavior.
                    # if step['thought']:
                    #    model_parts.append(types.Part(text=step['thought']))
                    
                    user_parts = []
                    for exc in step['tool_calls']:
                        # Function Call
                        model_parts.append(types.Part(
                            function_call=types.FunctionCall(name=exc.tool_name, args=exc.arguments)
                        ))
                        
                        # Function Response
                        result_data = exc.result
                        if exc.status == "failed":
                            result_data = {"error": exc.error}
                        
                        user_parts.append(
                            types.Part.from_function_response(name=exc.tool_name, response=result_data)
                        )
                    
                    if model_parts:
                        history.append(types.Content(role="model", parts=model_parts))
                    
                    if user_parts:
                        history.append(types.Content(role="tool", parts=user_parts))

            except Exception as e:
                from app.core.logging import get_logger
                logger = get_logger(__name__)
                logger.warning(f"Failed to expand tool_executions for msg {msg.id}: {e}")

        # 2. Legacy Meta Data check (Backward Compatibility)
        elif msg.role == "model" and msg.meta_data and isinstance(msg.meta_data, list):
            try:
                for step in msg.meta_data:
                    # step is a dict: {'step_type': 'tool_execution', 'thought': '...', 'tool_calls': [...]}
                    
                    # A. Reconstruct Model Turn (Thought + Calls)
                    model_parts = []
                    thought = step.get("thought")
                    # Optimization: Exclude thoughts for legacy data as well
                    # if thought:
                    #     model_parts.append(types.Part(text=thought))
                    
                    tool_calls_data = step.get("tool_calls", [])
                    for tc in tool_calls_data:
                         # Gemini types.FunctionCall expected args: name, args
                         model_parts.append(types.Part(
                             function_call=types.FunctionCall(name=tc["name"], args=tc["args"])
                         ))
                    
                    if model_parts:
                        history.append(types.Content(role="model", parts=model_parts))

                    # B. Reconstruct User Turn (monitor/Results)
                    user_parts = []
                    for tc in tool_calls_data:
                        # tc has result, status, error
                        # types.Part.from_function_response expects: name, response
                        # response should be the result dict or error
                        result_data = tc.get("result")
                        
                        # Handle error case
                        if tc.get("status") == "failed":
                            result_data = {"error": tc.get("error")}
                        
                        user_parts.append(
                            types.Part.from_function_response(name=tc["name"], response=result_data)
                        )
                    
                    if user_parts:
                        history.append(types.Content(role="tool", parts=user_parts))
            except Exception as e:
                # Fallback: If parsing fails, just log warning and proceed to add content
                # This ensures we don't break the whole chat if valid history exists but metadata is malformed
                from app.core.logging import get_logger
                logger = get_logger(__name__)
                logger.warning(f"Failed to expand message metadata for msg {msg.id}: {e}")

        # 2. Add the final message content
        # For Assistant, this is the "Final Answer" after tools.
        # For User, this is the user's prompt.
        if msg.content:
             history.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

    # Check if the last message in history is the same as the user_message
    # This prevents duplication if the message was already saved to DB and fetched
    if not history or history[-1].parts[0].text != user_message:
        history.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

    return history
