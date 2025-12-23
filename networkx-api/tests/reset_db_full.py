import os
import sys

# Add backend to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend"))
sys.path.append(backend_path)

from common.models import Base
from app.core.database import engine


def reset_db():
    print("Resetting database using Backend models...")

    # Verify tables
    print(f"Tables found in metadata: {list(Base.metadata.tables.keys())}")

    # Drop all tables
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    print("Recreating tables...")
    Base.metadata.create_all(bind=engine)
    print("Database reset complete.")


if __name__ == "__main__":
    reset_db()
