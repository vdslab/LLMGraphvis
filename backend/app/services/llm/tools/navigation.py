import json
from google.genai import types
from app import models
from app.core.logging import get_logger

logger = get_logger(__name__)

definitions = [
    types.FunctionDeclaration(
        name="switch_to_parent_network",
        description="Switch the active view back to the parent network (if currently viewing a subgraph).",
        parameters=types.Schema(type="OBJECT", properties={})
    ),
    types.FunctionDeclaration(
        name="switch_to_main_network",
        description="Switch the active view back to the original root network (the main graph).",
        parameters=types.Schema(type="OBJECT", properties={})
    )
]

async def switch_to_parent_network(args: dict, context: dict) -> dict:
    chat_id = context['chat_id']
    db = context['db']
    queue = context['queue']
    
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        return {"error": "Chat not found"}
        
    current_network = db.query(models.Network).filter(models.Network.id == chat.network_id).first()
    if not current_network or not current_network.parent_network_id:
        return {"status": "warning", "message": "Already at the root network or no parent found.", "network_id": chat.network_id}
        
    parent_id = current_network.parent_network_id
    chat.network_id = parent_id
    db.commit()
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Switching back to parent network (ID: {parent_id})..."})})
    
    return {"status": "success", "message": f"Switched to parent network (ID: {parent_id})", "network_id": parent_id}

async def switch_to_main_network(args: dict, context: dict) -> dict:
    chat_id = context['chat_id']
    db = context['db']
    queue = context['queue']
    
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        return {"error": "Chat not found"}

    # Traverse up to find the root
    current_network = db.query(models.Network).filter(models.Network.id == chat.network_id).first()
    while current_network.parent_network_id:
        current_network = db.query(models.Network).filter(models.Network.id == current_network.parent_network_id).first()
    
    if current_network.id == chat.network_id:
        return {"status": "warning", "message": "Already at the main network.", "network_id": chat.network_id}

    chat.network_id = current_network.id
    db.commit()
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Switching back to main network (ID: {current_network.id})..."})})
    
    return {"status": "success", "message": f"Switched to main network (ID: {current_network.id})", "network_id": current_network.id}

handlers = {
    "switch_to_parent_network": switch_to_parent_network,
    "switch_to_main_network": switch_to_main_network
}
