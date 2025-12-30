from functools import wraps
from app.core import database

def execute_with_db(func):
    """
    Decorator to inject a database session into the function.
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
    return wrapper


def safe_mcp_tool(func):
    """
    Decorator for MCP tools to provide:
    1. Automatic logging of inputs and outputs.
    2. Standardized error handling (returns {"error": ...} instead of raising).
    3. Safe truncation of large arguments in logs.
    """
    import functools
    from app.core.logging import get_logger
    
    # Use a logger specific to tools
    logger = get_logger("app.mcp.tools")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        
        # safely log arguments
        safe_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, str) and len(v) > 500:
                safe_kwargs[k] = f"{v[:500]}... [TRUNCATED]"
            else:
                safe_kwargs[k] = v
        
        safe_args = []
        for v in args:
             if isinstance(v, str) and len(v) > 500:
                safe_args.append(f"{v[:500]}... [TRUNCATED]")
             else:
                safe_args.append(v)

        logger.info(f"TOOL_START: {tool_name} | Args: {safe_args} | Kwargs: {safe_kwargs}")

        try:
            result = func(*args, **kwargs)
            # Log success (checking if result assumes error dict pattern generally used here)
            if isinstance(result, dict) and "error" in result:
                 logger.warning(f"TOOL_ERROR_RETURN: {tool_name} | Error: {result['error']}")
            else:
                 logger.info(f"TOOL_END: {tool_name} | Success")
            return result

        except Exception as e:
            import traceback
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            logger.error(f"TOOL_EXCEPTION: {tool_name} | {error_msg}\n{stack_trace}")
            return {"error": f"Tool execution failed: {error_msg}"}
            
    return wrapper
