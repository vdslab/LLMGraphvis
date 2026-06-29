from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger
from .providers.types import ToolDefinition

logger = get_logger(__name__)


async def _get_chat_and_network(chat_id: int, db: Session):
    """Helper to retrieve chat and its current network."""
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        return None, None, {"content": "Chat not found"}
        
    current_network = (
        db.query(models.Network)
        .filter(models.Network.id == chat.network_id)
        .first()
    )
    if not current_network:
        return chat, None, {"content": "Current network context not found"}
        
    return chat, current_network, None

async def switch_to_main_network(chat_id: int, db: Session) -> dict:
    """
    Switches the chat context back to the main (root) network.
    Use this when the user wants to go back to the original full graph.
    """
    try:
        chat, current_network, error_response = _get_chat_and_network(chat_id, db)
        if error_response:
            return error_response


        # Traverse up to find the root
        root_network = current_network
        while root_network.parent_network_id is not None:
            parent = (
                db.query(models.Network)
                .filter(models.Network.id == root_network.parent_network_id)
                .first()
            )
            if parent:
                root_network = parent
            else:
                break

        # Update chat context
        chat.network_id = root_network.id
        db.commit()

        return {"content": f"Context switched to Main Network (ID: {root_network.id})."}

    except Exception as e:
        logger.error(f"Error in switch_to_main_network: {e}")
        return {"content": f"Failed to switch to main network: {str(e)}"}


async def switch_to_parent_network(chat_id: int, db: Session) -> dict:
    """
    Switches the chat context to the parent network of the current subgraph.
    Use this when the user wants to go up one level in the hierarchy.
    """
    try:
        chat, current_network, error_response = _get_chat_and_network(chat_id, db)
        if error_response:
            return error_response


        if current_network.parent_network_id is None:
            return {
                "content": "Already at the top-level network. Cannot switch to parent."
            }

        # Update chat context
        chat.network_id = current_network.parent_network_id
        db.commit()

        return {
            "content": f"Context switched to Parent Network (ID: {current_network.parent_network_id})."
        }

    except Exception as e:
        logger.error(f"Error in switch_to_parent_network: {e}")
        return {"content": f"Failed to switch to parent network: {str(e)}"}


def get_local_tools() -> list[ToolDefinition]:
    """Returns the list of local tools as provider-agnostic ToolDefinitions."""
    return [
        ToolDefinition(
            name="switch_to_main_network",
            description="Switches the chat context back to the main (root) network. Use this when the user wants to go back to the original full graph.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        ToolDefinition(
            name="switch_to_parent_network",
            description="Switches the chat context to the parent network of the current subgraph. Use this when the user wants to go up one level in the hierarchy.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
    ]


async def execute_local_tool(tool_name: str, arguments: dict, context: dict):
    """Executes a local tool."""
    chat_id = context.get("chat_id")
    db = context.get("db")

    if tool_name == "switch_to_main_network":
        return await switch_to_main_network(chat_id, db)
    elif tool_name == "switch_to_parent_network":
        return await switch_to_parent_network(chat_id, db)
    else:
        raise ValueError(f"Unknown local tool: {tool_name}")
