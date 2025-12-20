import sys
import os
import io
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add networkx-api to path
sys.path.append(os.path.join(os.getcwd(), "networkx-api"))

from app.core.database import Base
from app import models
from app.logic.importer import parse_and_save_graphml

# Use the container DB URL (assuming running from host but mapping works if port is exposed)
# But wait, earlier I found that localhost:5432 might be a different DB.
# However, I successfully dropped tables in the container DB using docker compose exec.
# And networkx-api recreated them.
# So if I want to verify, I should probably run this script INSIDE the container or fix my connection.

# Since I can't easily run python script inside container without copying it,
# I will try to connect to localhost:5432 again.
# If it fails to find tables, I know I'm hitting the wrong DB.
# But I can use the same trick: use docker compose exec to run psql to verify.

# Actually, I can use `docker compose exec networkx-api python3` to run a script if I mount it.
# The volume is `./networkx-api:/app`.
# So if I put the script in `networkx-api/verify_logic.py`, I can run it inside container.

def create_verification_script():
    script_content = """
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import SQLALCHEMY_DATABASE_URL
from app import models
from app.logic.importer import parse_and_save_graphml

def verify():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Clean up
    try:
        from sqlalchemy import text
        # Delete attribute values (children first)
        db.execute(text("DELETE FROM node_float_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = 999))"))
        db.execute(text("DELETE FROM node_text_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = 999))"))
        db.execute(text("DELETE FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = 999)"))
        
        db.execute(text("DELETE FROM edge_float_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = 999))"))
        db.execute(text("DELETE FROM edge_text_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = 999))"))
        db.execute(text("DELETE FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = 999)"))

        # Delete attributes
        db.execute(text("DELETE FROM node_attributes WHERE network_id = 999"))
        db.execute(text("DELETE FROM edge_attributes WHERE network_id = 999"))

        # Delete edges (references nodes)
        db.execute(text("DELETE FROM edges WHERE network_id = 999"))
        
        # Delete nodes
        db.execute(text("DELETE FROM nodes WHERE network_id = 999"))
        
        # Delete network
        db.execute(text("DELETE FROM networks WHERE id = 999"))
        
        db.commit()
        print("Cleaned up old test data.")
    except Exception as e:
        print(f"Cleanup failed: {e}")
        db.rollback()
    
    # Dummy GraphML
    graphml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="weight" attr.type="double"/>
  <key id="d1" for="node" attr.name="type" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="n0">
      <data key="d0">1.5</data>
      <data key="d1">A</data>
    </node>
    <node id="n1">
      <data key="d0">2.0</data>
      <data key="d1">B</data>
    </node>
  </graph>
</graphml>'''

    print("Parsing GraphML...")
    try:
        print("Calling parse_and_save_graphml...")
        parse_and_save_graphml(999, graphml, db)
        print("Parsed successfully.")
    except Exception as e:
        print(f"Failed: {e}")
        return

    # Verify
    print("Verifying attributes...")
    attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == 999).all()
    for attr in attrs:
        print(f"Attribute: {attr.attribute_name}, Type: {attr.data_type}")
        if attr.attribute_name == "weight" and attr.data_type != "float":
            print("FAILURE: weight should be float")
        if attr.attribute_name == "type" and attr.data_type != "string":
            print("FAILURE: type should be string")

if __name__ == "__main__":
    verify()
"""
    with open("networkx-api/verify_logic.py", "w") as f:
        f.write(script_content)

if __name__ == "__main__":
    create_verification_script()
