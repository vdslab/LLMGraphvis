import os
import sys
from sqlalchemy import create_engine, inspect

# Define DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/graphvis")

def verify_db():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Existing tables:", tables)
    
    if "node_attributes" in tables:
        columns = [c["name"] for c in inspector.get_columns("node_attributes")]
        print("node_attributes columns:", columns)
        if "data_type" in columns:
            print("SUCCESS: data_type column exists in node_attributes.")
        else:
            print("FAILURE: data_type column MISSING in node_attributes.")
    else:
        print("FAILURE: node_attributes table MISSING.")

    if "edge_attributes" in tables:
        columns = [c["name"] for c in inspector.get_columns("edge_attributes")]
        print("edge_attributes columns:", columns)
        if "data_type" in columns:
            print("SUCCESS: data_type column exists in edge_attributes.")
        else:
            print("FAILURE: data_type column MISSING in edge_attributes.")
    else:
        print("FAILURE: edge_attributes table MISSING.")

if __name__ == "__main__":
    verify_db()
