
import sys
import os
import logging

# Add current directory to path
sys.path.append(os.getcwd())

from app.core.database import get_db_context
from app.mcp.tools import retrieval
from common import models

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reproduce():
    with get_db_context() as db:
        # Create a dummy network and node
        network = models.Network(name="Test Network 500")
        db.add(network)
        db.commit()
        db.refresh(network)
        net_id = network.id
        logger.info(f"Created network {net_id}")

        node = models.Node(network_id=net_id, node_id="n500", label="Node 500")
        db.add(node)
        db.commit()

        # Try to get node details
        logger.info("Attempting get_node_details...")
        try:
            # Note: The tool returns a JSON string, not dict
            result = retrieval.get_node_details(
                network_id=net_id,
                node_id="n500"
            )
            logger.info(f"Success! Result: {result}")
        except Exception as e:
            logger.error(f"Caught error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    reproduce()
