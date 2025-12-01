import os
import sys
from sqlalchemy import create_engine, text, inspect

# Add networkx-api to path
sys.path.append(os.path.join(os.getcwd(), "networkx-api"))

from app.core.database import engine, Base
from app import models # Register models

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/graphvis")

def reset_db():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Try to drop tables
        # We need to drop in order of dependencies or use CASCADE
        tables_to_drop = ["nodes", "edges", "node_attributes", "edge_attributes", "node_attribute_values", "edge_attribute_values", "networks"]
        
        print("Dropping tables...")
        for table in tables_to_drop:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                print(f"Dropped {table}")
            except Exception as e:
                print(f"Failed to drop {table}: {e}")
        
        conn.commit()

    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")
    
    # Verify
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Existing tables:", tables)
    
    if "node_attributes" in tables:
        columns = [c["name"] for c in inspector.get_columns("node_attributes")]
        if "data_type" in columns:
            print("SUCCESS: data_type column exists.")
        else:
            print("FAILURE: data_type column MISSING.")

if __name__ == "__main__":
    reset_db()
