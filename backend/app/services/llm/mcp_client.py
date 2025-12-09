import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from google.genai import types

# NetworkX API Configuration
NETWORKX_API_URL = os.getenv("NETWORKX_API_URL", "http://networkx-api:8000")
SSE_ENDPOINT = f"{NETWORKX_API_URL}/mcp/sse"

async def get_tools_as_gemini_functions() -> list[types.Tool]:
    """
    Connects to the NetworkXAPI MCP Server, discovers tools, 
    and converts them to Gemini-compatible function declarations.
    """
    # Note: We use sse_client for HTTP/SSE connection
    async with sse_client(SSE_ENDPOINT, headers={"Host": "localhost:8001"}) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List tools from the MCP server
            result = await session.list_tools()
            tools = result.tools
            
            gemini_tools = []
            for tool in tools:
                gemini_tools.append(_convert_to_gemini(tool))
                
            # Wrap in a generic Tool object for Gemini
            return [types.Tool(function_declarations=gemini_tools)]

def _convert_to_gemini(mcp_tool) -> types.FunctionDeclaration:
    """
    Converts an MCP Tool definition to a Gemini FunctionDeclaration.
    """
    return types.FunctionDeclaration(
        name=mcp_tool.name,
        description=mcp_tool.description,
        parameters=mcp_tool.inputSchema
    )

async def execute_tool(tool_name: str, arguments: dict):
    """
    Executes a tool on the NetworkXAPI MCP Server.
    """
    async with sse_client(SSE_ENDPOINT, headers={"Host": "localhost:8001"}) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
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
                import json
                return json.loads(output_text)
            except:
                return output_text
