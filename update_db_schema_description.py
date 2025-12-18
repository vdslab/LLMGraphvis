from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql://takuma@localhost:5432/graphvis"

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

            # 4. networks.last_layout_name
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='networks' AND column_name='last_layout_name';"))
            if not result.fetchone():
                print("Adding visual config columns to 'networks'...")
                connection.execute(text("ALTER TABLE networks ADD COLUMN last_layout_name VARCHAR;"))
                connection.execute(text("ALTER TABLE networks ADD COLUMN last_node_size_config JSON;"))
                connection.execute(text("ALTER TABLE networks ADD COLUMN last_node_color_config JSON;"))
                connection.execute(text("ALTER TABLE networks ADD COLUMN last_edge_width_config JSON;"))
                connection.execute(text("ALTER TABLE networks ADD COLUMN last_edge_color_config JSON;"))
                connection.execute(text("ALTER TABLE networks ADD COLUMN last_node_label_config JSON;"))
            else:
                 print("Visual config columns in 'networks' already exist.")

            # 5. networks.graphml_content (Make Nullable)
            result = connection.execute(text("SELECT is_nullable FROM information_schema.columns WHERE table_name='networks' AND column_name='graphml_content';"))
            row = result.fetchone()
            if row and row[0] == 'NO':
                print("Altering 'graphml_content' to be NULLABLE...")
                connection.execute(text("ALTER TABLE networks ALTER COLUMN graphml_content DROP NOT NULL;"))
            else:
                print("'graphml_content' is already nullable or does not exist.")

            connection.commit()
            print("Migration completed successfully.")
            
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
