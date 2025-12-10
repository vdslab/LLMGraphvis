
import logging
import sys
import os
import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.getcwd(), "networkx-api"))

from app import models
from app.core.database import Base
from app.logic import centrality, layout, importer

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
        graphml = "".join(nx.generate_graphml(G))
        network_id = 999
        importer.parse_and_save_graphml(network_id, graphml, db)
        
        # 1. Test PageRank
        logger.info("Testing PageRank...")
        try:
            centrality.calculate_centrality(network_id, "pagerank", db)
            logger.info("PageRank calculation successful.")
        except Exception as e:
            logger.error(f"PageRank failed: {e}")
            raise e
            
        # Verify it was saved
        attr = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id, models.NodeAttribute.attribute_name == "pagerank_centrality").first()
        if not attr:
            raise AssertionError("pagerank_centrality attribute not created")
            
        # 2. Test Circle alias
        logger.info("Testing Circle Layout Alias...")
        try:
            layout.calculate_layout(network_id, "circle", db)
            logger.info("Circle layout successful.")
        except Exception as e:
            logger.error(f"Circle layout failed: {e}")
            raise e
            
        attr_x = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id, models.NodeAttribute.attribute_name == "circle_x").first()
        if not attr_x:
            raise AssertionError("circle_x attribute not created")

        # 3. Test ForceAtlas2 (Check if it's real or fallback)
        logger.info("Testing ForceAtlas2...")
        # We can't easily detect fallback from outside unless we check logs or exact coordinates, 
        # but let's at least run it.
        layout.calculate_layout(network_id, "forceatlas2", db)
        logger.info("ForceAtlas2 run successful (Note: might be fallback).")
        
        logger.info("VERIFICATION PASSED")
        
    except Exception as e:
        logger.error(f"VERIFICATION FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
