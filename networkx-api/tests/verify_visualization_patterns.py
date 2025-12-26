import sys
import os
import math

# Add networkx-api and root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
networkx_api_dir = os.path.abspath(os.path.join(current_dir, ".."))
root_dir = os.path.abspath(os.path.join(networkx_api_dir, ".."))

if networkx_api_dir not in sys.path:
    sys.path.append(networkx_api_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from common import models
from app.logic.visualization_builder import build_visualization, VisualizationBuilder
from app.logic import layout
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def create_test_data(db):
    network = models.Network(id=1, name="Verify Net")
    db.add(network)
    
    # Create 5 nodes
    # n0: type=A, score=10
    # n1: type=A, score=20
    # n2: type=B, score=30
    # n3: type=B, score=40
    # n4: type=C, score=50 (Top)
    nodes = []
    types = ["A", "A", "B", "B", "C"]
    scores = [10.0, 20.0, 30.0, 40.0, 50.0]
    
    for i in range(5):
        n = models.Node(network_id=1, node_id=f"n{i}", label=f"Node {i}")
        db.add(n)
        nodes.append(n)
    db.commit()
    
    # Create Attributes
    type_attr = models.NodeAttribute(network_id=1, attribute_name="type", data_type="text")
    score_attr = models.NodeAttribute(network_id=1, attribute_name="score", data_type="float")
    db.add(type_attr)
    db.add(score_attr)
    db.commit()
    
    # Assign Attributes
    navs = []
    text_vals = []
    float_vals = []
    
    nodes_map = {n.node_id: n.id for n in nodes}
    
    for i in range(5):
        # Type
        nav_t = models.NodeAttributeValue(node_id=nodes_map[f"n{i}"], attribute_id=type_attr.id)
        db.add(nav_t)
        db.flush()
        text_vals.append({"node_attribute_value_id": nav_t.id, "text_value": types[i]})
        
        # Score
        nav_s = models.NodeAttributeValue(node_id=nodes_map[f"n{i}"], attribute_id=score_attr.id)
        db.add(nav_s)
        db.flush()
        float_vals.append({"node_attribute_value_id": nav_s.id, "float_value": scores[i]})
        
    db.bulk_insert_mappings(models.NodeTextAttributeValue, text_vals)
    db.bulk_insert_mappings(models.NodeFloatAttributeValue, float_vals)
    db.commit()

    # Create Edges (Linear chain n0-n1-n2-n3-n4)
    # Weights: 1, 2, 3, 4
    attributes = []
    weight_vals = []
    weight_attr = models.EdgeAttribute(network_id=1, attribute_name="weight", data_type="float")
    db.add(weight_attr)
    db.commit()
    
    for i in range(4):
        e = models.Edge(
            network_id=1, 
            source_node_id=nodes_map[f"n{i}"], 
            target_node_id=nodes_map[f"n{i+1}"],
            edge_id=f"e{i}"
        )
        db.add(e)
        db.flush()
        
        nav_w = models.EdgeAttributeValue(edge_id=e.id, attribute_id=weight_attr.id)
        db.add(nav_w)
        db.flush()
        weight_vals.append({"edge_attribute_value_id": nav_w.id, "float_value": float(i+1)})

    db.bulk_insert_mappings(models.EdgeFloatAttributeValue, weight_vals)
    db.commit()

def test_node_color_categorical(db):
    print("\n--- Testing Node Color: CATEGORICAL ---")
    # Verify: Type A -> Red, Type B -> Blue, Type C -> Default (Green)
    config = {
        "attribute": "type",
        "scale_type": "CATEGORICAL",
        "color_map": {"A": "red", "B": "blue"},
        "default_color": "green",
        "fixed_mapping": True
    }
    
    vis = build_visualization(db, 1, node_color_config=config)
    nodes = {n["id"]: n for n in vis["nodes"]}
    
    # n0 (A) -> red
    assert nodes["n0"]["color"] == "red", f"n0 expected red, got {nodes['n0']['color']}"
    # n2 (B) -> blue
    assert nodes["n2"]["color"] == "blue", f"n2 expected blue, got {nodes['n2']['color']}"
    # n4 (C) -> green (default)
    assert nodes["n4"]["color"] == "green", f"n4 expected green (default), got {nodes['n4']['color']}"
    print("SUCCESS")

def test_node_color_linear(db):
    print("\n--- Testing Node Color: LINEAR ---")
    # Verify: Score 10 -> C1, Score 50 -> C2. Gradient Interpoolation.
    gradient = ["#000000", "#FFFFFF"] # black to white
    config = {
        "attribute": "score",
        "scale_type": "LINEAR",
        "gradient": gradient
    }
    
    vis = build_visualization(db, 1, node_color_config=config)
    nodes = {n["id"]: n for n in vis["nodes"]}
    
    # n0 (10) -> Should be black (#000000)
    # n4 (50) -> Should be white (#FFFFFF)
    # n2 (30) -> Should be gray (#808080 approx)
    
    print(f"n0 color: {nodes['n0']['color']}")
    print(f"n4 color: {nodes['n4']['color']}")
    
    # Check simple validity (RGB hex)
    assert nodes["n0"]["color"].lower() == "#000000", "Min value should match start gradient"
    assert nodes["n4"]["color"].lower() == "#ffffff", "Max value should match end gradient"
    print("SUCCESS")

def test_node_size_linear(db):
    print("\n--- Testing Node Size: LINEAR ---")
    # Verify: Score 10 -> Min(10), Score 50 -> Max(50)
    config = {
        "attribute": "score",
        "min": 10,
        "max": 50
    }
    
    vis = build_visualization(db, 1, node_size_config=config)
    nodes = {n["id"]: n for n in vis["nodes"]}
    
    # n0 (10) -> 10
    # n4 (50) -> 50
    # n2 (30) -> 30
    
    assert abs(nodes["n0"]["size"] - 10) < 0.1
    assert abs(nodes["n4"]["size"] - 50) < 0.1
    assert abs(nodes["n2"]["size"] - 30) < 0.1
    print("SUCCESS")

def test_edge_width_linear(db):
    print("\n--- Testing Edge Width: LINEAR ---")
    # Weights: 1, 2, 3, 4. Min=1, Max=4.
    config = {
        "attribute": "weight",
        "min": 1.0,
        "max": 4.0
    }
    
    vis = build_visualization(db, 1, edge_width_config=config)
    edges = vis["links"]
    # We need to map edges back to IDs. 
    # e0: n0->n1 (weight 1)
    # e3: n3->n4 (weight 4)
    
    # Since edges list order isn't guaranteed, we look at values
    widths = sorted([e["width"] for e in edges])
    print(f"Widths: {widths}")
    
    assert abs(widths[0] - 1.0) < 0.1
    assert abs(widths[-1] - 4.0) < 0.1
    print("SUCCESS")

def test_layout_switch(db):
    print("\n--- Testing Layout Switch ---")
    # 1. Calc ForceAtlas2
    # 2. Calc Circular
    # Verify coordinates change
    
    layout.calculate_layout(1, "forceatlas2", db)
    vis_fa2 = build_visualization(db, 1, layout_name="forceatlas2")
    n0_fa2 = (vis_fa2["nodes"][0]["x"], vis_fa2["nodes"][0]["y"])
    
    layout.calculate_layout(1, "circular", db)
    vis_circ = build_visualization(db, 1, layout_name="circular")
    n0_circ = (vis_circ["nodes"][0]["x"], vis_circ["nodes"][0]["y"])
    
    print(f"FA2 Pos: {n0_fa2}")
    print(f"Circ Pos: {n0_circ}")
    
    # They should be different (unless purely coincidental, which is unlikely for these layouts)
    assert n0_fa2 != n0_circ
    print("SUCCESS")

def run():
    db = setup_db()
    try:
        create_test_data(db)
        
        test_node_color_categorical(db)
        test_node_color_linear(db)
        test_node_size_linear(db)
        test_edge_width_linear(db)
        test_layout_switch(db)
        
        print("\nAll Visualization Pattern Tests PASSED.")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run()
