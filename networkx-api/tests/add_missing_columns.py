
from app.core.database import engine
from sqlalchemy import text

def add_columns():
    print("Attempting to add missing columns to 'networks' table...")
    
    commands = [
        "ALTER TABLE networks ADD COLUMN IF NOT EXISTS description TEXT;",
        "ALTER TABLE networks ADD COLUMN IF NOT EXISTS last_layout_name VARCHAR;",
        "ALTER TABLE networks ADD COLUMN IF NOT EXISTS last_node_size_config JSON;",
        "ALTER TABLE networks ADD COLUMN IF NOT EXISTS last_node_color_config JSON;",
        "ALTER TABLE networks ADD COLUMN IF NOT EXISTS last_edge_width_config JSON;",
        "ALTER TABLE networks ADD COLUMN IF NOT EXISTS last_edge_color_config JSON;",
        "ALTER TABLE networks ADD COLUMN IF NOT EXISTS last_node_label_config JSON;"
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            try:
                print(f"Executing: {cmd}")
                conn.execute(text(cmd))
                conn.commit()
                print("Success.")
            except Exception as e:
                print(f"Error executing {cmd}: {e}")

if __name__ == "__main__":
    add_columns()
