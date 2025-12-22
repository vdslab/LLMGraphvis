import os
import sys
import time

import networkx as nx

# Add current directory to path so we can import app modules
sys.path.append(os.getcwd())

from app import models
from app.core.database import SessionLocal
from app.logic.centrality import calculate_centrality
from app.logic.importer import parse_and_save_graphml
from app.logic.subgraph import create_largest_component_subgraph
from app.logic.visualization_builder import VisualizationBuilder


def cleanup_network(db, net_id):
    try:
        # Delete subgraphs first
        db.query(models.Network).filter(
            models.Network.parent_network_id == net_id
        ).delete()
        db.query(models.Network).filter(models.Network.id == net_id).delete()
        db.commit()
    except Exception as e:
        print(f"Cleanup warning: {e}")
        db.rollback()


def create_random_graphml():
    # Create a graph with 2 components: one large, one small
    # 1000 nodes, density 0.01 (approx 5000 edges)
    G = nx.erdos_renyi_graph(1000, 0.01, seed=42)

    # Add a small disconnected component
    G.add_edge("isolate1", "isolate2")

    # Convert to GraphML
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<graph id="G" edgedefault="undirected">',
    ]

    for n in G.nodes():
        lines.append(f'<node id="{n}"/>')
    for u, v in G.edges():
        lines.append(f'<edge source="{u}" target="{v}"/>')

    lines.append("</graph></graphml>")
    return "\n".join(lines)


def test_workflow():
    db = SessionLocal()
    net_id = 8888

    try:
        cleanup_network(db, net_id)

        print("1. Uploading Graph (1000 nodes + 2 isolates)...")
        start = time.time()
        graphml = create_random_graphml()
        net_id = parse_and_save_graphml(net_id, graphml, db)
        db.commit()
        print(f"   Created Network ID: {net_id} (Time: {time.time() - start:.2f}s)")

        print("\n2. executing create_largest_component_subgraph...")
        start = time.time()
        res = create_largest_component_subgraph(net_id, db)
        print(f"   LCC extraction time: {time.time() - start:.2f}s")
        sub_id = res["new_network_id"]
        print(f"   Created Subgraph ID: {sub_id} ({res['name']})")

        # Verify LCC size (should be 1000)
        sub_node_count = (
            db.query(models.Node).filter(models.Node.network_id == sub_id).count()
        )
        print(f"   Subgraph Node Count: {sub_node_count} (Expected 1000)")

        print("\n3. executing calculate_centrality (degree)...")
        start = time.time()
        calculate_centrality(sub_id, "degree", db)
        print(f"   Centrality calculation time: {time.time() - start:.2f}s")

        # Verify Attribute Creation
        attr = (
            db.query(models.NodeAttribute)
            .filter(
                models.NodeAttribute.network_id == sub_id,
                models.NodeAttribute.attribute_name == "degree_centrality",
            )
            .first()
        )

        if not attr:
            print("   FAIL: degree_centrality attribute NOT created!")
        else:
            print("   SUCCESS: degree_centrality attribute exists.")

        print("\n4. executing VisualizationBuilder (with sizing by degree)...")
        start = time.time()
        vb = VisualizationBuilder(
            network_id=sub_id,
            db=db,
            node_size_config={
                "attribute": "degree_centrality",
                "scale_type": "LINEAR",
                "min_size": 5,
                "max_size": 20,
            },
            node_color_config={"scale_type": "FIXED", "default_color": "#cccccc"},
        )
        vb.validate_and_prepare()
        vb.fetch_data()
        vb.calculate_statistics()
        vis_data = vb.build()
        print(f"   Visualization time: {time.time() - start:.2f}s")

        # Check node sizes
        nodes = vis_data["nodes"]
        sizes = [n["size"] for n in nodes]
        print(f"   Generated {len(sizes)} node sizes.")
        print(f"   Sample sizes: {sizes[:5]}")

        if all(s == 10 for s in sizes):  # Default size if mapping failed
            print("   FAIL: Sizes seem to be default (10)?")
        else:
            print("   SUCCESS: Sizes vary.")

        # Check layout coords
        if nodes[0]["x"] == 0.0 and nodes[0]["y"] == 0.0:
            print("   WARNING: Layout seems to be 0,0?")

        print("\nWORKFLOW SUCCESSFUL")

    except Exception as e:
        print(f"\nWORKFLOW FAILED: {e}")
        import traceback

        traceback.print_exc()
    finally:
        cleanup_network(db, net_id)
        db.close()


if __name__ == "__main__":
    test_workflow()
