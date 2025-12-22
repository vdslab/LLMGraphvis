import os
import sys

# Add app to path
sys.path.append(os.getcwd())

from app import models
from app.core.database import SessionLocal
from app.logic.importer import parse_and_save_graphml
from app.logic.subgraph import create_subgraph_from_nodes
from app.logic.visualization_builder import VisualizationBuilder

# SQLALCHEMY_DATABASE_URL = "sqlite:///./test_repro.db"
# engine = create_engine(SQLALCHEMY_DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)


def cleanup_network(db, net_id):
    # Cascade delete is usually handled by DB or models, but let's be explicit if needed
    # For now, just deleting the network object should cascade if configured,
    # but safe way is to delete sub-objects if cascade not guaranteed.
    # Assuming cascade works for this test.
    db.query(models.Network).filter(models.Network.parent_network_id == net_id).delete()
    db.query(models.Network).filter(models.Network.id == net_id).delete()
    db.commit()


def test_repro():
    db = SessionLocal()
    net_id = 9999
    try:
        try:
            cleanup_network(db, net_id)
        except Exception as e:
            print(
                f"Warning: Cleanup failed: {e}. Proceeding with new network or collision handling."
            )
            db.rollback()

        # 1. Create Network with Many Nationalities (Stress Test)
        # We'll use parse_and_save_graphml to simulate real data flow
        graph_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
            '<key id="d0" for="node" attr.name="nationality" attr.type="string"/>',
            '<graph id="G" edgedefault="undirected">',
        ]

        # Generator 50 nodes, 20 nationalities
        import random

        # Ensure consistent nationalities for test
        random.seed(42)
        nationalities = [f"Nation_{i}" for i in range(20)]

        node_ids = []
        for i in range(50):
            nat = nationalities[i % len(nationalities)]
            graph_lines.append(f'<node id="n{i}"><data key="d0">{nat}</data></node>')
            node_ids.append(f"n{i}")

        # Add some edges
        for i in range(49):
            graph_lines.append(f'<edge source="n{i}" target="n{i + 1}"/>')

        graph_lines.append("</graph></graphml>")
        graphml = "\n".join(graph_lines)

        print("Uploading GraphML (Stress Test)...")
        net_id = parse_and_save_graphml(net_id, graphml, db)
        print(f"Using Network ID: {net_id}")
        db.commit()

        # Verify Attributes
        print("Verifying Node Attributes...")
        attrs = (
            db.query(models.NodeAttribute)
            .filter(models.NodeAttribute.network_id == net_id)
            .all()
        )
        for a in attrs:
            print(f" - {a.attribute_name} ({a.data_type})")

        # 2. Check Coloring Logic
        print("\nChecking Coloring Logic...")
        vb = VisualizationBuilder(
            network_id=net_id,
            db=db,
            node_color_config={"attribute": "nationality", "scale_type": "CATEGORICAL"},
        )
        vb.validate_and_prepare()
        vb.fetch_data()
        vb.calculate_statistics()

        cmap = vb.categorical_color_map
        print(f"Categorical Map Size: {len(cmap)}")
        print(f"Categorical Map: {cmap}")

        if len(cmap) < 2:
            print("FAIL: Expected multiple colors in map!")
        elif len(cmap) > 11:  # 10 + maybe manual overrides?
            print("INFO: More than 10 colors?")
        else:
            print("SUCCESS: Colors generated (Top 10).")

        # 3. Create Subgraph (first 20 nodes)
        target_nodes = [f"n{i}" for i in range(20)]
        print(f"\nCreating Subgraph with {len(target_nodes)} nodes...")
        res = create_subgraph_from_nodes(net_id, target_nodes, db)
        sub_id = res["new_network_id"]

        # 4. Verify Subgraph Attributes
        print(f"Verifying Subgraph {sub_id} Attributes...")
        sub_attrs = (
            db.query(models.NodeAttribute)
            .filter(models.NodeAttribute.network_id == sub_id)
            .all()
        )
        sub_attr_names = [a.attribute_name for a in sub_attrs]
        print(f"Subgraph Attrs: {sub_attr_names}")

        if "nationality" not in sub_attr_names:
            print("FAIL: 'nationality' attribute NOT inherited!")
        else:
            print("SUCCESS: 'nationality' inherited.")

        # Verify Values
        print("Verifying Subgraph Values...")
        # Get 'nationality' attr id
        nat_attr = next(
            (a for a in sub_attrs if a.attribute_name == "nationality"), None
        )
        if nat_attr:
            vals = (
                db.query(models.NodeTextAttributeValue)
                .join(models.NodeAttributeValue)
                .filter(models.NodeAttributeValue.attribute_id == nat_attr.id)
                .all()
            )
            print(f"Found {len(vals)} 'nationality' values in subgraph (Expected 20).")

            if len(vals) < 20:
                print(
                    f"FAIL: Expected 20 values, found {len(vals)}! Attribute Copy Failed!"
                )
            else:
                print("SUCCESS: All values copied.")

        # 5. Verify Smart Inference (Regression Test for "Single Color" default)
        print("\nChecking Smart Inference...")
        vb_auto = VisualizationBuilder(
            network_id=net_id,
            db=db,
            node_color_config={"attribute": "nationality"},  # Missing scale_type!
        )
        vb_auto.validate_and_prepare()
        vb_auto.fetch_data()
        vb_auto.calculate_statistics()

        if vb_auto.node_color_config.get("scale_type") == "CATEGORICAL":
            print("SUCCESS: Inference inferred CATEGORICAL from string attribute.")
            print(f"Auto Map Size: {len(vb_auto.categorical_color_map)}")
        else:
            print(
                f"FAIL: Inference failed. Scale Type: {vb_auto.node_color_config.get('scale_type')}"
            )

    finally:
        db.close()
        # Clean up
        if os.path.exists("test_repro.db"):
            os.remove("test_repro.db")


if __name__ == "__main__":
    test_repro()
