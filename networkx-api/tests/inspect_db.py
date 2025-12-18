
from app.core.database import SessionLocal
from sqlalchemy import text

def inspect_schema():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'networks'"))
        columns = result.fetchall()
        print("Columns in 'networks' table:")
        for col in columns:
            print(f"- {col[0]} ({col[1]})")
            
        print("-" * 20)
        # Check node_attributes
        result = db.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'node_attributes'"))
        columns = result.fetchall()
        print("Columns in 'node_attributes' table:")
        for col in columns:
            print(f"- {col[0]} ({col[1]})")

    finally:
        db.close()

if __name__ == "__main__":
    inspect_schema()
