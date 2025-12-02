import sys
import os
import json

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal
from app import models

def check_chat_state(chat_id):
    db = SessionLocal()
    try:
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat:
            print(f"Chat {chat_id} not found.")
            return

        print(f"Chat ID: {chat.id}")
        print(f"Name: {chat.name}")
        
        if chat.visualization_state:
            print("Visualization State: FOUND")
            if isinstance(chat.visualization_state, dict):
                keys = chat.visualization_state.keys()
                print(f"Keys: {list(keys)}")
                if "config" in chat.visualization_state:
                    print(f"Config: {json.dumps(chat.visualization_state['config'], indent=2)}")
                if "data" in chat.visualization_state:
                    data = chat.visualization_state["data"]
                    print(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    if isinstance(data, dict) and "nodes" in data:
                        print(f"Node count: {len(data['nodes'])}")
                        if len(data['nodes']) > 0:
                            print(f"Sample node: {data['nodes'][0]}")
            else:
                print(f"State type: {type(chat.visualization_state)}")
                print(f"Content: {chat.visualization_state}")
        else:
            print("Visualization State: NONE")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        chat_id = int(sys.argv[1])
    else:
        chat_id = 4
    check_chat_state(chat_id)
