import json
import os

from google.genai import types
from mcp import ClientSession
from mcp.client.sse import sse_client

from app.core.logging import get_logger

logger = get_logger(__name__)

# NetworkX API Configuration
NETWORKX_API_URL = os.getenv("NETWORKX_API_URL", "http://networkx-api:8000")
SSE_ENDPOINT = f"{NETWORKX_API_URL}/mcp/sse"


# Cache for tools
_tools_cache = None

async def get_tools_as_gemini_functions() -> list[types.Tool]:
    """
    Connects to the NetworkXAPI MCP Server, discovers tools,
    Converts MCP tools to Gemini function declarations.
    """
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache

    # Note: We use sse_client for HTTP/SSE connection
    async with sse_client(SSE_ENDPOINT) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List tools from the MCP server
            result = await session.list_tools()
            tools = result.tools

            gemini_tools_list = []
            for tool in tools:
                fd = _convert_to_gemini(tool)
                gemini_tools_list.append(types.Tool(function_declarations=[fd]))

            # Add read_resource client-side tool
            gemini_tools_list.append(
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="read_resource",
                            description="Reads a resource from the MCP server using its URI.",
                            parameters={
                                "type": "OBJECT",
                                "properties": {
                                    "uri": {
                                        "type": "STRING",
                                        "description": "The URI of the resource to read (e.g., network://1/attributes/nodes)",
                                    }
                                },
                                "required": ["uri"],
                            },
                        )
                    ]
                )
            )
            
            _tools_cache = gemini_tools_list
            return gemini_tools_list


def _convert_to_gemini(mcp_tool) -> types.FunctionDeclaration:
    """
    Converts an MCP Tool definition to a Gemini FunctionDeclaration.
    """
    tool_name = str(getattr(mcp_tool, "name", None) or mcp_tool.get("name"))
    tool_desc = str(
        getattr(mcp_tool, "description", None) or mcp_tool.get("description")
    )
    tool_schema = getattr(mcp_tool, "inputSchema", None) or mcp_tool.get("inputSchema")

    # Sanitize schema: remove 'title' which can confuse some parsers
    if tool_schema:
        # First resolve references ($ref) using $defs if present
        if "$defs" in tool_schema or "definitions" in tool_schema:
            tool_schema = _resolve_schema_refs(tool_schema, tool_schema)

        tool_schema = _sanitize_schema(tool_schema)

    return types.FunctionDeclaration(
        name=tool_name, description=tool_desc, parameters=tool_schema
    )


def _resolve_schema_refs(schema: dict, root: dict) -> dict:
    """
    Recursively resolves $ref in JSON schema by looking up definitions in root.
    Removes $defs/definitions from the final output.
    """
    if not isinstance(schema, dict):
        return schema

    # If this is a reference, resolve it
    if "$ref" in schema:
        ref_path = schema["$ref"]
        # Basic support for local refs like "#/$defs/MyType"
        if ref_path.startswith("#/"):
            parts = ref_path.split("/")
            # Navigate the root to find the definition
            definition = root
            for part in parts[1:]:
                definition = definition.get(part)
                if definition is None:
                    break

            if definition:
                # Recursively resolve the found definition
                return _resolve_schema_refs(definition, root)

        # If we can't resolve it, return as is (or handle error)
        return schema

    new_schema = {}
    for key, value in schema.items():
        # Skip definitions in the output as they are resolved inline
        if key in ["$defs", "definitions"]:
            continue

        if isinstance(value, dict):
            new_schema[key] = _resolve_schema_refs(value, root)
        elif isinstance(value, list):
            new_schema[key] = [
                _resolve_schema_refs(item, root) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            new_schema[key] = value

    return new_schema


def _sanitize_schema(schema: dict) -> dict:
    """Recursively remove 'title' from JSON schema."""
    if not isinstance(schema, dict):
        return schema

    new_schema = schema.copy()
    if "title" in new_schema:
        del new_schema["title"]
    # Double check for residual $defs if they weren't caught before (though _resolve handles them)
    if "$defs" in new_schema:
        del new_schema["$defs"]

    for key, value in new_schema.items():
        if isinstance(value, dict):
            new_schema[key] = _sanitize_schema(value)
        elif isinstance(value, list):
            new_schema[key] = [
                _sanitize_schema(item) if isinstance(item, dict) else item
                for item in value
            ]

    return new_schema


from contextlib import asynccontextmanager

@asynccontextmanager
async def session_scope():
    """
    Context manager that yields a connected ClientSession.
    Usage:
        async with session_scope() as session:
             await session.call_tool(...)
    """
    try:
        async with sse_client(SSE_ENDPOINT) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    except Exception as e:
        logger.error(f"MCP Session connection failed: {e}")
        raise

async def execute_tool(tool_name: str, arguments: dict, session: ClientSession = None):
    """
    Executes a tool on the NetworkXAPI MCP Server.
    If 'session' is provided, it uses the existing session.
    Otherwise, it creates a transient session (old behavior).
    """
    # Sanitize arguments for logging (truncate large strings)
    log_args = arguments.copy()
    for k, v in log_args.items():
        if isinstance(v, str) and len(v) > 100:
            log_args[k] = v[:100] + "..."

    logger.info(f"Executing tool: {tool_name} with arguments: {log_args}")

    if session:
        return await _execute_internal(session, tool_name, arguments)
    
    # Transient session
    async with session_scope() as new_session:
        return await _execute_internal(new_session, tool_name, arguments)

async def _execute_internal(session: ClientSession, tool_name: str, arguments: dict):
    try:
        # Handle client-side tools
        if tool_name == "read_resource":
            uri = arguments.get("uri")
            result = await session.read_resource(uri)
            # Resource content is a list of ReadResourceResult
            # We assume text content for now
            parsed_result = json.loads(result.contents[0].text)
            if isinstance(parsed_result, list):
                return {"result": parsed_result}
            return parsed_result

        result = await session.call_tool(tool_name, arguments)

        if result.isError:
            raise RuntimeError(f"Tool execution failed: {result.content}")

        # MCP returns a list of content (TextContent, ImageContent, etc.)
        # For our use case, we mostly expect simplified text/JSON back.
        # We'll join text content.
        output_text = ""
        for content in result.content:
            if content.type == "text":
                output_text += content.text

        # Try parsing as JSON if possible, otherwise return string
        try:
            parsed_result = json.loads(output_text)
            if isinstance(parsed_result, list):
                return {"result": parsed_result}
            return parsed_result
        except:
            return {"content": output_text}

    except Exception as e:
        import traceback

        # Better handling for TaskGroup errors (Python 3.11+)
        if isinstance(e, BaseException): # BaseException covers all, but we check specifically for ExceptionGroup
            # In Python 3.11+, TaskGroup raises ExceptionGroup
            if type(e).__name__ == "ExceptionGroup" or isinstance(e, BaseExceptionGroup):
                logger.error(f"TaskGroup error in execute_tool '{tool_name}': {e}")
                for i, sub_exc in enumerate(e.exceptions):
                    logger.error(f"  Sub-exception {i+1}: {type(sub_exc).__name__}: {sub_exc}")
                    # If it's a connection error, it might be buried here
                    if "connection" in str(sub_exc).lower():
                        logger.error(f"  -> Likely connection issue with tool '{tool_name}'")
            else:
                 logger.error(f"Error executing tool {tool_name} with args {arguments}: {e}")
        else:
            logger.error(f"Error executing tool {tool_name} with args {arguments}: {e}")

        traceback.print_exc()
        raise


async def get_resource(uri: str, session: ClientSession = None) -> dict:
    """
    Directly reads a resource from the MCP server.
    Useful for internal context validation.
    """
    try:
        if session:
             return await _read_resource_internal(session, uri)

        async with session_scope() as session:
             return await _read_resource_internal(session, uri)
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        return {}

async def _read_resource_internal(session: ClientSession, uri: str) -> dict:
    result = await session.read_resource(uri)
    # Resource content is a list of ReadResourceResult
    # We assume text content for now
    parsed_result = json.loads(result.contents[0].text)
    return parsed_result
