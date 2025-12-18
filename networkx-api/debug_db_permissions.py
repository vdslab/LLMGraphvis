from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/graphvis"

def debug_permissions():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # Get current user
            user = connection.execute(text("SELECT current_user;")).fetchone()[0]
            print(f"Current DB User: {user}")
            
            # Get columns
            result = connection.execute(text("SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_name = 'networks';"))
            print("Columns in 'networks' table:")
            for row in result:
                print(row)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_permissions()
