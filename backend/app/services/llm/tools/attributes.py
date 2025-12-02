from google.genai import types
from app.services import network_service

definitions = [
    types.FunctionDeclaration(
        name="list_node_attributes",
        description="List all available node attributes for the network.",
        parameters=types.Schema(type="OBJECT", properties={})
    ),
    types.FunctionDeclaration(
        name="list_edge_attributes",
        description="List all available edge attributes for the network.",
        parameters=types.Schema(type="OBJECT", properties={})
    )
]

async def list_node_attributes(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    result = await network_service.list_node_attributes(network_id)
    return {"attributes": result}

async def list_edge_attributes(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    result = await network_service.list_edge_attributes(network_id)
    return {"attributes": result}

handlers = {
    "list_node_attributes": list_node_attributes,
    "list_edge_attributes": list_edge_attributes
}
