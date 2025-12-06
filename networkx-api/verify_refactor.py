
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import SQLALCHEMY_DATABASE_URL
from app import models
from app.logic import importer, layout, centrality, subgraph

def verify():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Clean up 888 and any subgraphs
    try:
        from sqlalchemy import text
        # Simple nuclear cleanup for verify script
        db.execute(text("DELETE FROM networks WHERE id = 888"))
        # Also clean up subgraphs if any (hard to know IDs, but parent_network_id=888)
        db.execute(text("DELETE FROM networks WHERE parent_network_id = 888"))
        db.commit()
    except Exception as e:
        print(f"Cleanup failed (expected if not exists): {e}")
        db.rollback()
    
    # 1. Import
    graphml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <node id="n2"/>
    <edge source="n0" target="n1"/>
    <edge source="n1" target="n2"/>
  </graph>
</graphml>'''
    
    print("Testing importer...")
    importer.parse_and_save_graphml(888, graphml, db)
    
    # 2. Test Layout
    print("Testing layout...")
    layout.calculate_layout(888, "spring", db)
    # Check attributes
    attr_x = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == 888, models.NodeAttribute.attribute_name == "spring_x").first()
    if not attr_x:
        print("FAILURE: spring_x attribute not found")
        return
    print("Layout OK.")

    # 3. Test Centrality
    print("Testing centrality...")
    centrality.calculate_centrality(888, "degree", db)
    attr_c = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == 888, models.NodeAttribute.attribute_name == "degree_centrality").first()
    if not attr_c:
        print("FAILURE: degree_centrality attribute not found")
        return
    print("Centrality OK.")
    
    # 4. Test Subgraph (Ego)
    print("Testing ego network...")
    # Ego for n1 (center) with r=1 should include n0, n1, n2
    result = subgraph.create_ego_network(888, "n1", 1, db)
    new_id = result["new_network_id"]
    print(f"Ego network created: {new_id}")
    
    new_net = db.query(models.Network).filter(models.Network.id == new_id).first()
    if not new_net:
        print("FAILURE: New network not found")
        return
        
    print(f"New network contents: {new_net.graphml_content}")
    if "graphml" not in new_net.graphml_content:
         print("FAILURE: graphml_content is suspicious")

    # Check nodes count
    count = db.query(models.Node).filter(models.Node.network_id == new_id).count()
    if count != 3:
        print(f"FAILURE: Expected 3 nodes in ego network, got {count}")
    else:
        print("Subgraph count OK.")

    print("Success!")

if __name__ == "__main__":
    verify()
