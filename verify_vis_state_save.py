import asyncio
import os
import json
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app import models
from app.services.llm import service as llm_service
from unittest.mock import MagicMock, AsyncMock

# Mock network_service to avoid actual API calls
llm_service.network_service = AsyncMock()
llm_service.network_service.generate_visualization.return_value = {
    "nodes": [],
    "edges": [],
    "options": {"layout": "spring"}
}

async def verify_vis_state_save():
    db: Session = SessionLocal()
    try:
        # Create a dummy user and chat
        user = db.query(models.User).filter(models.User.username == "test_verifier").first()
        if not user:
            user = models.User(username="test_verifier", hashed_password="hashed_password")
            db.add(user)
            db.commit()
            db.refresh(user)

        # Create a dummy network
        network = models.Network(name="Test Network", graphml_content="<graphml></graphml>")
        db.add(network)
        db.commit()
        db.refresh(network)

        chat = models.Chat(name="Test Chat", user_id=user.id, network_id=network.id)
        db.add(chat)
        db.commit()
        db.refresh(chat)

        print(f"Created test chat with ID: {chat.id}")

        # Simulate generate_visualization tool call
        queue = asyncio.Queue()
        function_name = "generate_visualization"
        function_args = {
            "layout_name": "spring",
            "node_size_config": {"attribute": "degree_centrality", "min": 5, "max": 20}
        }
        
        # Execute the tool
        # Note: We are calling _execute_single_tool directly which is an internal function, 
        # but it's the most direct way to test the saving logic.
        # We need to access it from the module.
        
        print("Executing generate_visualization tool...")
        result = await llm_service._execute_single_tool(
            function_name, 
            function_args, 
            network.id, 
            queue, 
            chat.id, 
            db
        )
        
        print(f"Tool execution result: {result}")

        # Verify database update
        db.refresh(chat)
        if chat.visualization_state:
            print("SUCCESS: visualization_state was saved to the database.")
            state = chat.visualization_state
            if isinstance(state, dict) and "config" in state and "data" in state:
                print("SUCCESS: visualization_state has correct structure (config and data).")
                print(f"Config: {state['config']}")
            else:
                print(f"FAILURE: visualization_state has incorrect structure: {state.keys() if isinstance(state, dict) else state}")
        else:
            print("FAILURE: visualization_state was NOT saved to the database.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if 'chat' in locals() and chat and chat.id:
            # We must fetch recent object from DB or merge it to delete
            db.merge(chat)
            db.delete(chat)
        if 'network' in locals() and network and network.id:
            db.merge(network)
            db.delete(network)
        # User cleanup might be skipped if we want to reuse it or if it existed before
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_vis_state_save())
