from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/graphvis"

def check():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("Connecting to database...")
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='chats' AND column_name='visualization_state';"))
            if result.fetchone():
                print("SUCCESS: Column 'visualization_state' exists.")
            else:
                print("FAILURE: Column 'visualization_state' DOES NOT exist.")
    except Exception as e:
        print(f"Check failed: {e}")

if __name__ == "__main__":
    check()
