import logging
import traceback
from functools import wraps

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from app.core import database

logger = logging.getLogger(__name__)


class ToolExecutionError(ToolError, RuntimeError):
    """Expose actionable failures while retaining internal RuntimeError callers."""


def execute_with_db(func):
    """Decorator to inject a database session into the function.

    The session is automatically closed after execution.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        db = database.SessionLocal()
        try:
            return func(db, *args, **kwargs)
        except Exception as e:
            # We can log here if needed, or just re-raise
            raise e
        finally:
            db.close()

    return wrapper


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
