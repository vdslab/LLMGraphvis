import os
import sys
from sqlalchemy import create_engine, text

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.database import engine
from app import models

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/graphvis")

def repair_schema():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Checking if chat_messages table exists and has correct columns...")
        # Check if table exists
        result = conn.execute(text("SELECT to_regclass('chat_messages')"))
        if not result.scalar():
            print("Table chat_messages does not exist. Creating it...")
            # We can use Alembic or just SQLAlchemy create_all for this table?
            # Or just raw SQL for simplicity in this repair script
            try:
                conn.execute(text("""
                    CREATE TABLE chat_messages (
                        id SERIAL PRIMARY KEY,
                        chat_id INTEGER NOT NULL REFERENCES chats(id),
                        role VARCHAR NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                conn.execute(text("CREATE INDEX ix_chat_messages_id ON chat_messages (id)"))
                conn.commit()
                print("SUCCESS: Created chat_messages table.")
            except Exception as e:
                print(f"FAILED to create table: {e}")
        else:
            # Check columns
            try:
                conn.execute(text("SELECT chat_id FROM chat_messages LIMIT 1"))
                print("Column chat_id exists.")
            except Exception:
                print("Column chat_id DOES NOT EXIST. Dropping and recreating table (simplest fix for dev)...")
                try:
                    conn.rollback()
                    conn.execute(text("DROP TABLE chat_messages CASCADE"))
                    conn.execute(text("""
                        CREATE TABLE chat_messages (
                            id SERIAL PRIMARY KEY,
                            chat_id INTEGER NOT NULL REFERENCES chats(id),
                            role VARCHAR NOT NULL,
                            content TEXT NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_chat_messages_id ON chat_messages (id)"))
                    conn.commit()
                    print("SUCCESS: Recreated chat_messages table.")
                except Exception as e:
                    print(f"FAILED to recreate table: {e}")

if __name__ == "__main__":
    repair_schema()
