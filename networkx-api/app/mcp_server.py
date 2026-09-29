import logging

# 1. Import the singleton MCP instance
from app.core.mcp import mcp

# 2. Import sub-modules to register Tools and Resources.
# Procedures ("prompts") are backend skills, not MCP prompts (ADR 0027).
# These imports are "side-effects" (they decorate functions on the 'mcp' object)
import app.mcp.tools
import app.mcp.resources

# Setup logging
from app.core.logging import get_logger
logger = get_logger(__name__)
logger.info("MCP Server initialized and tools registered.")

# The 'mcp' object is now populated and ready to run by the FastMCP entrypoint (uvicorn/cli)
