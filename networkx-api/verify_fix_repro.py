
import sys
import os
import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.append(os.getcwd())

from app import models
from app.database import Base
from app.logic.importer import parse_and_save_graphml
from app.logic.style_service import StyleService
from app.logic.subgraph import create_subgraph_from_nodes
from app.logic.visualization_builder import VisualizationBuilder

# Setup DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_repro.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def test_repro():
    db = SessionLocal()
    try:
        # 1. Create Network with Nationality
        # We'll use parse_and_save_graphml to simulate real data flow
        graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns 
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="nationality" attr.type="string"/>
  <key id="d1" for="node" attr.name="weight" attr.type="double"/>
  <graph id="G" edgedefault="undirected">
    <node id="n0">
      <data key="d0">US</data>
      <data key="d1">10.0</data>
    </node>
    <node id="n1">
      <data key="d0">UK</data>
      <data key="d1">20.0</data>
    </node>
    <node id="n2">
      <data key="d0">US</data>
      <data key="d1">15.0</data>
    </node>
    <node id="n3">
      <data key="d0">JP</data>
      <data key="d1">5.0</data>
    </node>
    <edge source="n0" target="n1"/>
    <edge source="n1" target="n2"/>
  </graph>
</graphml>
"""
        print("Uploading GraphML...")
        net_id = 999
        parse_and_save_graphml(net_id, graphml, db)
        db.commit()
        
        # Verify Attributes
        print("Verifying Node Attributes...")
        attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == net_id).all()
        for a in attrs:
            print(f" - {a.attribute_name} ({a.data_type})")
            
        # 2. Check Coloring Logic
        print("\nChecking Coloring Logic...")
        vb = VisualizationBuilder(
            network_id=net_id,
            db=db,
            node_color_config={"attribute": "nationality", "scale_type": "CATEGORICAL"}
        )
        vb.fetch_data()
        vb.calculate_statistics()
        
        cmap = vb.categorical_color_map
        print(f"Categorical Map: {cmap}")
        
        if len(cmap) < 2:
            print("FAIL: Expected multiple colors in map!")
        else:
            print("SUCCESS: Colors generated.")

        # 3. Create Subgraph
        print("\nCreating Subgraph (n0, n1)...")
        res = create_subgraph_from_nodes(net_id, ["n0", "n1"], db)
        sub_id = res["new_network_id"]
        
        # 4. Verify Subgraph Attributes
        print(f"Verifying Subgraph {sub_id} Attributes...")
        sub_attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == sub_id).all()
        sub_attr_names = [a.attribute_name for a in sub_attrs]
        print(f"Subgraph Attrs: {sub_attr_names}")
        
        if "nationality" not in sub_attr_names:
            print("FAIL: 'nationality' attribute NOT inherited!")
        else:
            print("SUCCESS: 'nationality' inherited.")
            
        # Verify Values
        print("Verifying Subgraph Values...")
        # Get 'nationality' attr id
        nat_attr = next((a for a in sub_attrs if a.attribute_name == "nationality"), None)
        if nat_attr:
            vals = db.query(models.NodeTextAttributeValue).join(models.NodeAttributeValue).filter(
                models.NodeAttributeValue.attribute_id == nat_attr.id
            ).all()
            print(f"Found {len(vals)} 'nationality' values in subgraph.")
            for v in vals:
                print(f" - Value: {v.text_value}")
                
            if len(vals) == 0:
                 print("FAIL: Attribute definition exists but NO values copied!")

    finally:
        db.close()
        # Clean up
        if os.path.exists("test_repro.db"):
            os.remove("test_repro.db")

if __name__ == "__main__":
    test_repro()
