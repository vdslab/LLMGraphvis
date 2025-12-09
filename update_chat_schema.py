import os
import sys
from sqlalchemy import create_engine, text

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.database import engine
from app import models

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/graphvis")

def update_schema():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Checking if visualization_state column exists in chats table...")
        try:
            conn.execute(text("SELECT visualization_state FROM chats LIMIT 1"))
            print("Column verification_state ALREADY EXISTS.")
        except Exception:
            print("Column verification_state DOES NOT EXIST. Adding it...")
            try:
                # Rollback current transaction to clear error
                conn.rollback() 
                conn.execute(text("ALTER TABLE chats ADD COLUMN visualization_state JSONB"))
                conn.commit()
                print("SUCCESS: Added visualization_state column.")
            except Exception as e:
                print(f"FAILED to add column: {e}")
                
if __name__ == "__main__":
    update_schema()
