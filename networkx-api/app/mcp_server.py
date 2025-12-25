import logging

# 1. Import the singleton MCP instance
from app.core.mcp import mcp

# 2. Import sub-modules to register Tools, Resources, and Prompts
# These imports are "side-effects" (they decorate functions on the 'mcp' object)
import app.mcp.tools
import app.mcp.resources
import app.mcp.prompts

# Setup logging
from app.core.logging import get_logger
logger = get_logger(__name__)
logger.info("MCP Server initialized and tools registered.")

# The 'mcp' object is now populated and ready to run by the FastMCP entrypoint (uvicorn/cli)
