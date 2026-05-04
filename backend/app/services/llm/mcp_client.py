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

    async with session_scope() as session:

            # List tools from the MCP server
            result = await session.list_tools()
            tools = result.tools

            gemini_tools_list = []
            for tool in tools:
                fd = _convert_to_gemini(tool)
                gemini_tools_list.append(types.Tool(function_declarations=[fd]))

            # Add client-side tools
            gemini_tools_list.extend([
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
                ),
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="list_resources",
                            description="Lists all available resources on the MCP server.",
                            parameters={
                                "type": "OBJECT",
                                "properties": {},
                            },
                        )
                    ]
                ),
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="list_prompts",
                            description="Lists all available prompts on the MCP server.",
                            parameters={
                                "type": "OBJECT",
                                "properties": {},
                            },
                        )
                    ]
                ),
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="get_prompt",
                            description="Gets a prompt from the MCP server by name, with optional arguments.",
                            parameters={
                                "type": "OBJECT",
                                "properties": {
                                    "name": {
                                        "type": "STRING",
                                        "description": "The name of the prompt to retrieve.",
                                    },
                                    "arguments": {
                                        "type": "OBJECT",
                                        "description": "Arguments for the prompt template.",
                                    }
                                },
                                "required": ["name"],
                            },
                        )
                    ]
                )
            ])
            
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
        _log_exception_details(e, "MCP Session connection")
        raise _unwrap_exception(e) from e

def _unwrap_exception(e: BaseException) -> BaseException:
    """
    Unwraps an ExceptionGroup if it contains only a single exception.
    """
    try:
        if isinstance(e, BaseExceptionGroup):
            if len(e.exceptions) == 1:
                return _unwrap_exception(e.exceptions[0])
    except NameError:
        pass # Pre-3.11
    return e

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
        # Handle client-side tools
        if tool_name == "read_resource":
            uri = arguments.get("uri")
            result = await session.read_resource(uri)
            # Inspect the first content item (assuming single file for now)
            content_item = result.contents[0]
            
            # naive mimeType check
            mime = getattr(content_item, "mimeType", None) or "text/plain"
            
            if "application/json" in mime:
                 try:
                    parsed_result = json.loads(content_item.text)
                    if isinstance(parsed_result, list):
                        return {"result": parsed_result}
                    return parsed_result
                 except json.JSONDecodeError:
                    # Fallback to text if JSON parse fails despite mimeType
                    return {"content": content_item.text, "error": "Invalid JSON"}
            
            # Default: Return as text wrapped in dict
            return {"content": content_item.text}

        if tool_name == "list_resources":
            result = await session.list_resources()
            # Convert Resource objects to dicts
            resources = [{"uri": r.uri, "name": r.name, "description": r.description, "mimeType": r.mimeType} for r in result.resources]
            return {"resources": resources}

        if tool_name == "list_prompts":
            result = await session.list_prompts()
            # Convert Prompt objects to dicts
            prompts = [{"name": p.name, "description": p.description, "arguments": [a.model_dump() for a in p.arguments] if p.arguments else []} for p in result.prompts]
            return {"prompts": prompts}

        if tool_name == "get_prompt":
            name = arguments.get("name")
            args = arguments.get("arguments", {})
            result = await session.get_prompt(name, args)
            # PromptResult has messages
            messages = [{"role": m.role, "content": m.content.text} for m in result.messages]
            return {"messages": messages}

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
        _log_exception_details(e, f"executing tool {tool_name} with args {arguments}")
        traceback.print_exc()
        raise _unwrap_exception(e) from e


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
        _log_exception_details(e, f"reading resource {uri}")
        return {}

async def _read_resource_internal(session: ClientSession, uri: str) -> dict:
    result = await session.read_resource(uri)
    content_item = result.contents[0]
    
    mime = getattr(content_item, "mimeType", None) or "text/plain"
    
    if "application/json" in mime:
         try:
            return json.loads(content_item.text)
         except Exception:
            # Fallback
            return {}
            
    # If not JSON, we might return empty or handle differently.
    # For internal context usage, we expect dictionaries.
    return {}


def _log_exception_details(e: BaseException, context: str):
    """
    Helper to log exception details, unwrapping ExceptionGroup if present.
    """
    # Python 3.11+ ExceptionGroup / BaseExceptionGroup handling
    is_group = False
    try:
        if isinstance(e, BaseExceptionGroup): # Checks for ExceptionGroup too as it inherits
             is_group = True
    except NameError:
        pass # Pre-3.11 environment

    if is_group:
        logger.error(f"TaskGroup/ExceptionGroup error in {context}: {e}")
        if hasattr(e, "exceptions"):
            for i, sub_exc in enumerate(e.exceptions):
                logger.error(f"  Sub-exception {i+1}: {type(sub_exc).__name__}: {sub_exc}")
                if "connection" in str(sub_exc).lower():
                    logger.error(f"  -> Likely connection issue in {context}")
    else:
        logger.error(f"Error in {context}: {e}")
