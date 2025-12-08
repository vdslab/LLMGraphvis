from sqlalchemy import create_engine, text
import os

# DB Connection URL
# Host is localhost because we are running from the host machine (agent env)
# Port is 5432 as exposed in docker compose
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/graphvis"

def migrate():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("Connecting to database...")
            # Check if column exists
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='chats' AND column_name='visualization_state';"))
            if result.fetchone():
                print("Column 'visualization_state' already exists.")
            else:
                print("Adding column 'visualization_state'...")
                connection.execute(text("ALTER TABLE chats ADD COLUMN visualization_state JSON;"))
                connection.commit()
                print("Column added successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
