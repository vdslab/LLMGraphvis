import logging
import traceback
from functools import wraps

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ToolExecutionError(ToolError, RuntimeError):
    """Expose actionable failures while retaining internal RuntimeError callers."""


def handle_tool_errors(func):
    """Decorator to handle errors in MCP tools.

    Catches validation errors and other exceptions, returning a clear error message.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.error(f"Validation error in {func.__name__}: {e}")
            raise ToolExecutionError(f"Invalid parameters provided: {e}") from e
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            logger.error(traceback.format_exc())
            raise ToolExecutionError(f"Tool execution failed: {str(e)}") from e

    return wrapper
