import logging
import sys
import os

# Add networkx-api to path
sys.path.insert(0, os.path.join(os.getcwd(), "networkx-api"))

from app.core.database import get_db_context
from app.logic import centrality, community, layout
from common import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_refactor():
    with get_db_context() as db:
        logger.info("Starting Refactor Verification")
        
        # 1. Setup Test Network
        # Check if network 1 exists, if not create basic one equivalent
        network = db.query(models.Network).first()
        if not network:
            logger.error("No network found in DB. Please run with a populated DB or create one.")
            return

        network_id = network.id
        logger.info(f"Using Network ID: {network_id}")

        # 2. Verify Centrality
        logger.info("--- Testing Centrality (Degree) ---")
        try:
            res = centrality.calculate_centrality(network_id, "degree", db)
            logger.info("Calculate Centrality: Success")
            
            # Use new check: check DB for attribute
            attr = db.query(models.NodeAttribute).filter_by(network_id=network_id, attribute_name="degree_centrality").first()
            if attr:
                 val_count = db.query(models.NodeAttributeValue).filter_by(attribute_id=attr.id).count()
                 logger.info(f"DB Check: Attribute '{attr.attribute_name}' has {val_count} values.")
            else:
                 logger.error("DB Check: Attribute 'degree_centrality' NOT FOUND.")
        except Exception as e:
            logger.error(f"Centrality Failed: {e}")
            import traceback
            traceback.print_exc()

        # 3. Verify Community
        logger.info("--- Testing Community (Louvain) ---")
        try:
            # Note: This should now create 'louvain_community'
            attr_name = community.calculate_community(network_id, "louvain", db)
            logger.info(f"Calculate Community: Success, created '{attr_name}'")
            
            attr = db.query(models.NodeAttribute).filter_by(network_id=network_id, attribute_name="louvain_community").first()
            if attr:
                 val_count = db.query(models.NodeAttributeValue).filter_by(attribute_id=attr.id).count()
                 logger.info(f"DB Check: Attribute '{attr.attribute_name}' has {val_count} values.")
            else:
                 logger.error("DB Check: Attribute 'louvain_community' NOT FOUND.")
            
        except Exception as e:
             logger.error(f"Community Failed: {e}")
             import traceback
             traceback.print_exc()

        # 4. Verify Layout
        logger.info("--- Testing Layout (Fruchterman-Reingold / Spring) ---")
        try:
            # Using 'spring' as it's deterministic-ish and standard
            layout.calculate_layout(network_id, "spring", db)
            logger.info("Calculate Layout: Success")
            
            attr_x = db.query(models.NodeAttribute).filter_by(network_id=network_id, attribute_name="spring_x").first()
            attr_y = db.query(models.NodeAttribute).filter_by(network_id=network_id, attribute_name="spring_y").first()
            
            if attr_x and attr_y:
                 count_x = db.query(models.NodeAttributeValue).filter_by(attribute_id=attr_x.id).count()
                 count_y = db.query(models.NodeAttributeValue).filter_by(attribute_id=attr_y.id).count()
                 logger.info(f"DB Check: spring_x has {count_x}, spring_y has {count_y} values.")
            else:
                 logger.error("DB Check: Layout attributes 'spring_x'/'spring_y' NOT FOUND.")

        except Exception as e:
             logger.error(f"Layout Failed: {e}")
             import traceback
             traceback.print_exc()

if __name__ == "__main__":
    verify_refactor()
