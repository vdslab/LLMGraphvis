import sys
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core import database
from app import models
from app.mcp_server import (
    list_node_attributes, 
    calculate_centrality, 
    get_top_nodes,
    create_ego_network,
    create_subgraph_from_nodes,
    create_largest_component_subgraph,
    get_subgraphs
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify():
    db = database.SessionLocal()
    try:
        # 1. Setup Data
        network = db.query(models.Network).filter(models.Network.name == "VerifyTestNetwork").first()
        if not network:
            # Recreate if missing (unlikely if previous step ran)
            network = models.Network(name="VerifyTestNetwork", description="Test Network")
            db.add(network)
            db.commit()
            db.refresh(network)
        
        logger.info(f"Using network {network.id}")
        
        # Ensure nodes/edges exist (idempotent check)
        nodes = db.query(models.Node).filter(models.Node.network_id == network.id).all()
        if not nodes:
            logger.warning("No nodes found, adding some...")
            for i in range(1, 6):
                db.add(models.Node(network_id=network.id, node_id=f"n{i}", label=f"Node {i}"))
            db.commit()
            nodes = db.query(models.Node).filter(models.Node.network_id == network.id).all()
        
        if not db.query(models.Edge).filter(models.Edge.network_id == network.id).first():
             # Star graph
             center = nodes[0]
             for i in range(1, 5):
                db.add(models.Edge(network_id=network.id, edge_id=f"{center.node_id}-{nodes[i].node_id}", source_node_id=center.id, target_node_id=nodes[i].id))
             db.commit()

        # 5. Test create_ego_network
        logger.info("--- Testing create_ego_network ---")
        try:
            # Radius 1 from n1 should include all nodes (n1..n5)
            res = create_ego_network(network.id, "n1", 1)
            logger.info(f"Ego network result: {res}")
            
            if 'network' in res and 'network_id' in res:
                sub_id = res['network_id']
                logger.info(f"Created Ego Network ID: {sub_id}")
                
                # Verify node count in DB
                sub_nodes_count = db.query(models.Node).filter(models.Node.network_id == sub_id).count()
                logger.info(f"Subgraph nodes count: {sub_nodes_count} (Expected 5)")
                if sub_nodes_count == 5:
                    logger.info("Ego Network Verify: OK")
                else:
                    logger.error(f"Ego Network Verify: FAIL. Expected 5, got {sub_nodes_count}")
            else:
                logger.error("Ego network result invalid")

        except Exception as e:
             logger.error(f"Error in create_ego_network: {e}")
             import traceback
             traceback.print_exc()

        # 6. Test create_subgraph_from_nodes
        logger.info("--- Testing create_subgraph_from_nodes ---")
        try:
            # Subgraph with n2, n3 (should have 0 edges as they are not connected directly)
            res = create_subgraph_from_nodes(network.id, ["n2", "n3"])
            logger.info(f"Subgraph from nodes result keys: {res.keys()}")
            
            sub_id = res['network_id']
            sub_nodes_count = db.query(models.Node).filter(models.Node.network_id == sub_id).count()
            logger.info(f"Subgraph nodes count: {sub_nodes_count} (Expected 2)")
            
            sub_edges_count = db.query(models.Edge).filter(models.Edge.network_id == sub_id).count()
            logger.info(f"Subgraph edges count: {sub_edges_count} (Expected 0)")
            
            if sub_nodes_count == 2 and sub_edges_count == 0:
                 logger.info("Subgraph from Nodes Verify: OK")
            else:
                 logger.error("Subgraph from Nodes Verify: FAIL")

        except Exception as e:
             logger.error(f"Error in create_subgraph_from_nodes: {e}")

        # 7. Test get_subgraphs
        logger.info("--- Testing get_subgraphs ---")
        try:
            subs = get_subgraphs(network.id)
            logger.info(f"Subgraphs list: {subs}")
            if len(subs) >= 2:
                 logger.info("Get Subgraphs Verify: OK")
            else:
                 logger.error(f"Get Subgraphs Verify: FAIL. Expected >= 2, got {len(subs)}")
        except Exception as e:
             logger.error(f"Error in get_subgraphs: {e}")

    except Exception as e:
        logger.error(f"General error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify()
