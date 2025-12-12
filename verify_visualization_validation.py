
import logging
import sys
import os
import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure we can import the app modules
sys.path.append(os.path.join(os.getcwd(), "networkx-api"))

from app import models
from app.core.database import Base
from app.logic import layout, importer, visualizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def run_verification():
    init_db()
    db = TestingSessionLocal()
    
    try:
        # Create a simple graph
        G = nx.karate_club_graph()
        # Add a real attribute to verify correct usage works
        nx.set_node_attributes(G, "USA", "nationality")
        
        graphml = "".join(nx.generate_graphml(G))
        network_id = 999
        importer.parse_and_save_graphml(network_id, graphml, db)
        
        # Calculate layout so visualization works
        layout.calculate_layout(network_id, "forceatlas2", db)
        
        # 1. Test Valid Attribute (Control)
        logger.info("Testing Valid Attribute request...")
        try:
            visualizer.generate_visualization_data(
                network_id, db,
                node_color_config={"scale_type": "CATEGORICAL", "attribute": "nationality"}
            )
            logger.info("Valid attribute request passed (as expected).")
        except Exception as e:
            logger.error(f"Valid attribute request FAILED: {e}")
            raise e

        # 2. Test Invalid Attribute (The Fix Verification)
        logger.info("Testing Invalid Attribute request...")
        try:
            visualizer.generate_visualization_data(
                network_id, db,
                node_color_config={"scale_type": "CATEGORICAL", "attribute": "NON_EXISTENT_ATTRIBUTE"}
            )
            # If we get here, it failed to raise error
            raise AssertionError("Did not raise ValueError for non-existent attribute!")
        except ValueError as e:
            logger.info(f"Caught expected ValueError: {e}")
            if "Missing required attributes" not in str(e):
                logger.warning(f"Error message might be unclear: {e}")
            else:
                logger.info("Error message is clear.")
                
        except Exception as e:
             logger.error(f"Caught unexpected exception type: {type(e)}: {e}")
             raise e
        
        logger.info("VERIFICATION PASSED")
        
    except Exception as e:
        logger.error(f"VERIFICATION FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
