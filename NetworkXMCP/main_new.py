"""
NetworkX MCP Server - New Architecture
=====================================

This is the new MCP server implementation following best practices.
It can be used as a standalone MCP server or integrated with FastAPI.
"""

import sys
import logging
from typing import Dict, Any, Optional

# Setup proper MCP logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("networkx_mcp")

try:
    # Try to use the proper MCP server
    from server import mcp
    logger.info("Using proper MCP server implementation")

    if __name__ == "__main__":
        logger.info("Starting NetworkX MCP Server...")
        mcp.run()

except ImportError as e:
    logger.warning(f"MCP libraries not available: {e}")
    logger.info("Falling back to FastAPI implementation")

    # Fallback to the original FastAPI implementation
    try:
        from main import app
        import uvicorn

        if __name__ == "__main__":
            logger.info("Starting FastAPI server as fallback...")
            uvicorn.run(app, host="0.0.0.0", port=8001)

    except ImportError:
        logger.error("Neither MCP nor FastAPI implementation available")
        sys.exit(1)
