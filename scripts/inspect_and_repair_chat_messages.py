import os
import sys
from sqlalchemy import create_engine, text, inspect

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.database import engine
from app import models

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/graphvis")

def inspect_and_repair():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("chat_messages")]
    print(f"Current columns in chat_messages: {columns}")
    
    with engine.connect() as conn:
        if "chat_id" not in columns:
            print("Column chat_id is MISSING. Attempting to ADD it...")
            try:
                # We need to default it to something if there are existing rows, or make it nullable first
                # But since we can't delete rows easily if not owner?
                # Let's try adding as nullable first
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN chat_id INTEGER"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_chat_id ON chat_messages (chat_id)"))
                # If we want foreign key
                conn.execute(text("ALTER TABLE chat_messages ADD CONSTRAINT fk_chat_messages_chats FOREIGN KEY (chat_id) REFERENCES chats(id)"))
                
                conn.commit()
                print("SUCCESS: Added chat_id column.")
            except Exception as e:
                print(f"FAILED to add chat_id: {e}")
        else:
            print("Column chat_id already exists.")

if __name__ == "__main__":
    inspect_and_repair()
