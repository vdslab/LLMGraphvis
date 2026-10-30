"""The MCP server: the singleton `mcp` with every tool and resource registered.

`app.main` mounts `mcp` from here. Procedures ("prompts") are backend skills,
not MCP prompts (ADR 0027).
"""

from app.core.logging import get_logger
from app.core.mcp import mcp  # noqa: F401  (mcp re-exported)

# Imported for their side effect: the decorators register tools and resources
# on `mcp`, in import order.
import app.mcp.tools  # noqa: F401
import app.mcp.resources  # noqa: F401

logger = get_logger(__name__)
logger.info("MCP Server initialized; sync tools use bounded worker threads.")
