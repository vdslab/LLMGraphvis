from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/graphvis"

def migrate():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("Connecting to database...")
            
            # 1. networks.description
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='networks' AND column_name='description';"))
            if not result.fetchone():
                print("Adding column 'description' to 'networks'...")
                connection.execute(text("ALTER TABLE networks ADD COLUMN description TEXT;"))
            else:
                print("Column 'description' in 'networks' already exists.")

            # 2. node_attributes.description
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='node_attributes' AND column_name='description';"))
            if not result.fetchone():
                print("Adding column 'description' to 'node_attributes'...")
                connection.execute(text("ALTER TABLE node_attributes ADD COLUMN description TEXT;"))
            else:
                print("Column 'description' in 'node_attributes' already exists.")

            # 3. edge_attributes.description
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='edge_attributes' AND column_name='description';"))
            if not result.fetchone():
                print("Adding column 'description' to 'edge_attributes'...")
                connection.execute(text("ALTER TABLE edge_attributes ADD COLUMN description TEXT;"))
            else:
                print("Column 'description' in 'edge_attributes' already exists.")

            connection.commit()
            print("Migration completed successfully.")
            
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
