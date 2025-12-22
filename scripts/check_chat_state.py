import sys
import os
import json

print("Starting check_chat_state.py...")

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal
from app import models

def check_chat_state(chat_id):
    with open("chat_state_output.txt", "w") as f:
        f.write(f"Starting check for chat {chat_id}\n")
        db = SessionLocal()
        try:
            # List tables
            from sqlalchemy import text
            result = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = [row[0] for row in result]
            f.write(f"Tables in DB: {tables}\n")

            chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
            if not chat:
                f.write(f"Chat {chat_id} not found.\n")
                return

            f.write(f"Chat ID: {chat.id}\n")
            f.write(f"Name: {chat.name}\n")
            
            if chat.visualization_state:
                f.write("Visualization State: FOUND\n")
                if isinstance(chat.visualization_state, dict):
                    keys = chat.visualization_state.keys()
                    f.write(f"Keys: {list(keys)}\n")
                    if "config" in chat.visualization_state:
                        f.write(f"Config: {json.dumps(chat.visualization_state['config'], indent=2)}\n")
                    if "data" in chat.visualization_state:
                        data = chat.visualization_state["data"]
                        f.write(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}\n")
                        if isinstance(data, dict) and "nodes" in data:
                            f.write(f"Node count: {len(data['nodes'])}\n")
                            if len(data['nodes']) > 0:
                                f.write(f"Sample node: {data['nodes'][0]}\n")
                else:
                    f.write(f"State type: {type(chat.visualization_state)}\n")
                    f.write(f"Content: {chat.visualization_state}\n")
            else:
                f.write("Visualization State: NONE\n")

        except Exception as e:
            f.write(f"Error: {e}\n")
        finally:
            db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        chat_id = int(sys.argv[1])
    else:
        chat_id = 4
    check_chat_state(chat_id)
