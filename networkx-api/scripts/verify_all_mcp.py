"""Inspect live tool and resource registrations without modifying the database."""

import asyncio

from app.mcp_server import mcp


async def main():
    tools = await mcp.list_tools()
    templates = await mcp.list_resource_templates()
    for tool in tools:
        print(tool.name)
    for template in templates:
        print(template.uri_template, template.mime_type)


if __name__ == "__main__":
    asyncio.run(main())
