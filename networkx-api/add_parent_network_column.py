import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "graphvis")

SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)


def add_column():
    with engine.connect() as connection:
        try:
            # Check current user
            user_result = connection.execute(text("SELECT current_user"))
            print(f"Current user: {user_result.scalar()}")

            # Check table owner
            owner_result = connection.execute(
                text("SELECT tableowner FROM pg_tables WHERE tablename = 'networks'")
            )
            print(f"Table owner: {owner_result.scalar()}")

            # Check if column exists
            result = connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='networks' AND column_name='parent_network_id'"
                )
            )
            if result.fetchone():
                print("Column 'parent_network_id' already exists.")
                return

            print("Adding 'parent_network_id' column...")
            connection.execute(
                text(
                    "ALTER TABLE networks ADD COLUMN parent_network_id INTEGER REFERENCES networks(id)"
                )
            )
            connection.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    add_column()
