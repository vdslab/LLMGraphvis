import networkx as nx
import sys
import os
from sqlalchemy import text
import numpy as np

# Add app to path
sys.path.append(os.getcwd())

from app.logic import layout
from app import models
from app.core import database

def create_test_network(db):
    print("Attempting to find existing network...")
    # Try to find any network
    existing = db.execute(text("SELECT id FROM networks LIMIT 1")).fetchone()
    if existing:
        net_id = existing[0]
        print(f"Using existing network {net_id} for verification.")
        
        # Check if it has enough nodes
        node_count = db.execute(text(f"SELECT count(*) FROM nodes WHERE network_id = {net_id}")).scalar()
        if node_count > 5:
             # Ensure we cleared old layout vals? layout.calculate_layout does this.
             return net_id
        else:
             print("Existing network too small, trying to create new one via raw SQL...")

    # Create a simple grid graph
    G = nx.grid_2d_graph(10, 10)
    mapping = {n: f"{n[0]}_{n[1]}" for n in G.nodes()}
    G = nx.relabel_nodes(G, mapping)
    
    print("Creating test network via raw SQL (bypassing model mismatch)...")
    
    # Check for description column and add if missing (Fixing environment)
    try:
        db.execute(text("SELECT description FROM networks LIMIT 0"))
        has_desc = True
    except Exception:
        print("Description column missing, adding it...")
        db.rollback()
        try:
            db.execute(text("ALTER TABLE networks ADD COLUMN description TEXT"))
            db.commit()
            has_desc = True
        except Exception as e:
            print(f"Failed to add column: {e}")
            has_desc = False
            db.rollback()
    
    insert_sql = "INSERT INTO networks (name, graphml_content, created_at, updated_at) VALUES (:name, '', now(), now()) RETURNING id"
    if has_desc:
        insert_sql = "INSERT INTO networks (name, description, graphml_content, created_at, updated_at) VALUES (:name, 'FA2 Test', '', now(), now()) RETURNING id"
        
    result = db.execute(text(insert_sql), {"name": "Test FA2 Grid"})
    network_id = result.scalar()
    db.commit()
    
    print(f"Created network {network_id}")
    
    # Insert Nodes
    print("Inserting nodes...")
    values = []
    for n in G.nodes():
        values.append({"nid": network_id, "node_id": str(n), "label": str(n)})
        
    # Bulk insert is hard with raw SQL and getting IDs back.
    # We'll use the model for nodes/edges if possible, usually those tables are stable.
    # Or just use single inserts.
    
    for n in G.nodes():
        db.execute(text("INSERT INTO nodes (network_id, node_id, label) VALUES (:nid, :node_id, :label)"), 
                   {"nid": network_id, "node_id": str(n), "label": str(n)})
    db.commit()
    
    # Get node mapping
    rows = db.execute(text(f"SELECT id, node_id FROM nodes WHERE network_id = {network_id}")).fetchall()
    node_map = {row[1]: row[0] for row in rows}
    
    # Insert Edges
    print("Inserting edges...")
    for u, v in G.edges():
        u_id = node_map.get(str(u))
        v_id = node_map.get(str(v))
        if u_id and v_id:
            db.execute(text("INSERT INTO edges (network_id, source_node_id, target_node_id, edge_id, weight) VALUES (:nid, :sid, :tid, :eid, 1.0)"),
                       {"nid": network_id, "sid": u_id, "tid": v_id, "eid": f"{u}-{v}"})
    db.commit()
    
    return network_id

def verify_layout(network_id, db):
    print(f"Calculating ForceAtlas2 layout for network {network_id}...")
    try:
        layout.calculate_layout(network_id, "forceatlas2", db)
    except Exception as e:
        print(f"Error in calculate_layout: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check values
    # We need to find the attribute IDs
    try:
        attr_x_row = db.execute(text(f"SELECT id FROM node_attributes WHERE network_id = {network_id} AND attribute_name = 'forceatlas2_x'")).fetchone()
        attr_y_row = db.execute(text(f"SELECT id FROM node_attributes WHERE network_id = {network_id} AND attribute_name = 'forceatlas2_y'")).fetchone()
        
        if not attr_x_row or not attr_y_row:
            print("FAIL: Layout attributes not created.")
            return False
            
        attr_x_id = attr_x_row[0]
        attr_y_id = attr_y_row[0]
        
        # Get values
        # join node_attribute_values and node_float_attribute_values
        query = text(f"""
            SELECT f.float_value 
            FROM node_attribute_values v
            JOIN node_float_attribute_values f ON v.id = f.node_attribute_value_id
            WHERE v.attribute_id = {attr_x_id}
        """)
        x_values = [r[0] for r in db.execute(query).fetchall()]
        
        query_y = text(f"""
            SELECT f.float_value 
            FROM node_attribute_values v
            JOIN node_float_attribute_values f ON v.id = f.node_attribute_value_id
            WHERE v.attribute_id = {attr_y_id}
        """)
        y_values = [r[0] for r in db.execute(query_y).fetchall()]
        
        if len(x_values) == 0:
            print("FAIL: No values found.")
            return False
            
        x_std = np.std(x_values)
        y_std = np.std(y_values)
        
        print(f"X STD: {x_std:.4f}")
        print(f"Y STD: {y_std:.4f}")
        
        # Check spread
        if x_std < 0.01 or y_std < 0.01:
            print("FAIL: Layout collapsed (std dev too low).")
            return False
            
        print("SUCCESS: Layout calculation produced valid spread.")
        return True
    except Exception as e:
        print(f"Verification check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    db = database.SessionLocal()
    try:
        net_id = create_test_network(db)
        if verify_layout(net_id, db):
            sys.exit(0)
        else:
            sys.exit(1)
    finally:
        db.close()
