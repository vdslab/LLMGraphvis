
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import SQLALCHEMY_DATABASE_URL
from app import models
from app.logic.importer import parse_and_save_graphml
from app.logic import layout
from app.logic.visualizer import generate_visualization_data

def verify():
    # Setup DB
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    network_id = 998
    
    # Clean up (simplified for brevity, assuming cascade delete or manual clean if needed)
    try:
        from sqlalchemy import text
        # Simple nuclear option for the test ID
        db.execute(text(f"DELETE FROM networks WHERE id = {network_id}")) # Cascade should handle rest if set up, otherwise we might leave orphans but for test script it's ok usually if we re-create
        # Actually existing verify script did it manually, likely no cascade on some rels. Let's do a quick clean.
        # Minimal clean - errors ignored
        for table in ["node_float_attribute_values", "node_text_attribute_values", "node_attribute_values", 
                      "edge_float_attribute_values", "edge_text_attribute_values", "edge_attribute_values",
                      "node_attributes", "edge_attributes", "edges", "nodes", "networks"]:
            try:
                if table == "networks":
                    db.execute(text(f"DELETE FROM {table} WHERE id = {network_id}"))
                elif "attribute" in table:
                     pass # cascading from nodes/edges usually? If not, verify_layout_new.py logic was needed. 
                     # Let's hope for cascade or previous script run clean. 
                     # Re-using verify_layout_new.py's cleaning logic to be safe.
            except: pass
        
        # Proper clean from verify_layout_new.py
        db.execute(text(f"DELETE FROM node_float_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM node_text_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id})"))
        db.execute(text(f"DELETE FROM node_attributes WHERE network_id = {network_id}"))
        db.execute(text(f"DELETE FROM nodes WHERE network_id = {network_id}"))
        db.execute(text(f"DELETE FROM networks WHERE id = {network_id}"))
        db.commit()
    except Exception as e:
        print(f"Cleanup check: {e}")
        db.rollback()

    # Create GraphML with 'team' attribute
    graphml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="team" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="n0"><data key="d0">TeamA</data></node>
    <node id="n1"><data key="d0">TeamA</data></node>
    <node id="n2"><data key="d0">TeamB</data></node>
    <node id="n3"><data key="d0">TeamC</data></node>
    <node id="n4"><data key="d0">TeamB</data></node>
  </graph>
</graphml>'''

    try:
        parse_and_save_graphml(network_id, graphml, db)
        print("Test graph created successfully.")
    except Exception as e:
        print(f"Failed to create test graph: {e}")
        return

    # Calculate layout (needed for visualizer)
    layout.calculate_layout(network_id, "spring", db)

    # Test Categorical Coloring
    node_color_config = {
        "attribute": "team",
        "scale_type": "CATEGORICAL"
        # No color_map provided -> should be auto-generated
    }

    try:
        vis_data = generate_visualization_data(
            network_id=network_id,
            db=db,
            layout_name="spring",
            node_color_config=node_color_config
        )
        
        nodes = vis_data["nodes"]
        # n0 and n1 should be TeamA
        # n2 and n4 should be TeamB
        # n3 should be TeamC
        
        node_map = {n["id"]: n for n in nodes}
        
        team_a_color = node_map["n0"]["color"]
        team_a_color_2 = node_map["n1"]["color"]
        team_b_color = node_map["n2"]["color"]
        team_b_color_2 = node_map["n4"]["color"]
        team_c_color = node_map["n3"]["color"]
        
        print(f"TeamA Color: {team_a_color}")
        print(f"TeamB Color: {team_b_color}")
        print(f"TeamC Color: {team_c_color}")
        
        errors = []
        if team_a_color != team_a_color_2:
            errors.append("Nodes in same category (TeamA) have different colors!")
        if team_b_color != team_b_color_2:
            errors.append("Nodes in same category (TeamB) have different colors!")
        if team_a_color == team_b_color:
            errors.append("TeamA and TeamB have same color!")
        if team_a_color == team_c_color:
            errors.append("TeamA and TeamC have same color!")
        if team_b_color == team_c_color:
            errors.append("TeamB and TeamC have same color!")
            
        if not errors:
            print("SUCCESS: Categorical coloring verified!")
        else:
            print("FAILURE: Verification failed with errors:")
            for err in errors:
                print(f"- {err}")
                
    except Exception as e:
        print(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify()
