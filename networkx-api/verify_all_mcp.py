import logging
import os
import sys
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Setup path to import app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app import (
    mcp_server,  # Import the module to test
    models,
)
from app.core.database import Base

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def setup_db():
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def verify_all_tools():
    session = setup_db()

    # Patch get_db_session to return our test session
    with patch("app.mcp_server.get_db_session", return_value=session):
        print("\n=== Verifying All MCP Tools & Resources ===\n")

        # 1. initialize_network
        print("1. Testing initialize_network...")
        graphml = """
        <graphml xmlns="http://graphml.graphdrawing.org/xmlns">
            <key id="d0" for="node" attr.name="color" attr.type="string"/>
            <key id="d1" for="edge" attr.name="weight" attr.type="double"/>
            <graph id="G" edgedefault="undirected">
                <node id="n0"><data key="d0">red</data></node>
                <node id="n1"><data key="d0">blue</data></node>
                <node id="n2"><data key="d0">green</data></node>
                <edge source="n0" target="n1"><data key="d1">1.0</data></edge>
                <edge source="n1" target="n2"><data key="d1">2.0</data></edge>
            </graph>
        </graphml>
        """
        # Create a network record first as initialize_network expects existing ID usually?
        # Actually pipeline.initialize_network_pipeline might expect the ID to exist or creation?
        # Looking at pipeline.py (not shown but inferred), usually we pass an ID.
        # Let's create a placeholder network.
        net = models.Network(name="Test Network")
        session.add(net)
        session.commit()
        session.refresh(net)
        net_id = net.id

        res = mcp_server.initialize_network(net_id, graphml)
        if "error" in str(res).lower() and "Error" in str(res):
            print(f"FAILURE: initialize_network returned error: {res}")
        else:
            print("SUCCESS: initialize_network")

        # 2. get_network_metadata
        print("\n2. Testing get_network_metadata...")
        res = mcp_server.get_network_metadata(net_id)
        if "Test Network" in res:
            print("SUCCESS: get_network_metadata")
        else:
            print(f"FAILURE: get_network_metadata: {res}")

        # 3. get_node_attributes (The one we fixed!)
        print("\n3. Testing get_node_attributes...")
        res = mcp_server.get_node_attributes(net_id)
        if "color" in res and "red" in res:
            print("SUCCESS: get_node_attributes")
        else:
            print(f"FAILURE: get_node_attributes: {res}")

        # 4. get_edge_attributes
        print("\n4. Testing get_edge_attributes...")
        res = mcp_server.get_edge_attributes(net_id)
        if "weight" in res:
            print("SUCCESS: get_edge_attributes")
        else:
            print(f"FAILURE: get_edge_attributes: {res}")

        # 5. search_nodes
        print("\n5. Testing search_nodes...")
        res = mcp_server.search_nodes(net_id, "red")
        if "n0" in res:
            print("SUCCESS: search_nodes")
        else:
            print(f"FAILURE: search_nodes: {res}")

        # 6. calculate_centrality
        print("\n6. Testing calculate_centrality...")
        res = mcp_server.calculate_centrality(net_id, "degree")
        if "calculated" in res:
            print("SUCCESS: calculate_centrality")
        else:
            print(f"FAILURE: calculate_centrality: {res}")

        # 7. calculate_layout
        print("\n7. Testing calculate_layout...")
        res = mcp_server.calculate_layout(net_id, "spring")
        if "calculated" in res:
            print("SUCCESS: calculate_layout")
        else:
            print(f"FAILURE: calculate_layout: {res}")

        # 8. create_subgraph_from_nodes (Verified description copy here too)
        print("\n8. Testing create_subgraph_from_nodes...")
        res = mcp_server.create_subgraph_from_nodes(
            net_id, ["n0", "n1"], preserve_layout=False
        )
        if isinstance(res, dict) and "new_network_id" in res:
            sub_id = res["new_network_id"]
            print(f"SUCCESS: create_subgraph_from_nodes (New ID: {sub_id})")

            # Verify Description Copying in Subgraph
            # We need to check if 'color' attribute in sub_id has description if source had it.
            # In graphml above, we didn't explicitly set description in DB, but let's check basic copy.
            attr = (
                session.query(models.NodeAttribute)
                .filter(
                    models.NodeAttribute.network_id == sub_id,
                    models.NodeAttribute.attribute_name == "color",
                )
                .first()
            )
            if attr:
                print("SUCCESS: Attribute 'color' copied to subgraph.")
            else:
                print("FAILURE: Attribute 'color' NOT copied to subgraph.")
        else:
            print(f"FAILURE: create_subgraph_from_nodes: {res}")

        # 9. get_subgraphs_resource
        print("\n9. Testing get_subgraphs_resource...")
        res = mcp_server.get_subgraphs_resource(net_id)
        if "Subgraph" in res:
            print("SUCCESS: get_subgraphs_resource")
        else:
            print(f"FAILURE: get_subgraphs_resource: {res}")

        # 10. create_ego_network
        print("\n10. Testing create_ego_network...")
        res = mcp_server.create_ego_network(net_id, "n1", 1)
        if isinstance(res, dict) and "new_network_id" in res:
            print("SUCCESS: create_ego_network")
        else:
            print(f"FAILURE: create_ego_network: {res}")

        # 11. create_path_subgraph
        print("\n11. Testing create_path_subgraph...")
        res = mcp_server.create_path_subgraph(net_id, "n0", "n2")
        if isinstance(res, dict) and "new_network_id" in res:
            print("SUCCESS: create_path_subgraph")
        else:
            print(f"FAILURE: create_path_subgraph: {res}")

        # 12. create_largest_component_subgraph
        print("\n12. Testing create_largest_component_subgraph...")
        res = mcp_server.create_largest_component_subgraph(net_id)
        if isinstance(res, dict) and "new_network_id" in res:
            print("SUCCESS: create_largest_component_subgraph")
        else:
            print(f"FAILURE: create_largest_component_subgraph: {res}")

        # 13. get_structure_resource
        print("\n13. Testing get_structure_resource...")
        res = mcp_server.get_structure_resource(net_id)
        if "node_count" in res:
            print("SUCCESS: get_structure_resource")
        else:
            print(f"FAILURE: get_structure_resource: {res}")

        # 14. Prompts (Just checking they run without error)
        print("\n14. Testing Prompts...")
        try:
            mcp_server.analyze_structure_prompt(net_id)
            print("SUCCESS: analyze_structure_prompt")
            mcp_server.recommend_visualization_prompt(net_id)
            print("SUCCESS: recommend_visualization_prompt")
            mcp_server.investigate_attributes_prompt(net_id)
            print("SUCCESS: investigate_attributes_prompt")
            mcp_server.find_important_nodes_prompt(net_id)
            print("SUCCESS: find_important_nodes_prompt")
        except Exception as e:
            print(f"FAILURE: Prompt raised exception: {e}")

    session.close()


if __name__ == "__main__":
    verify_all_tools()
