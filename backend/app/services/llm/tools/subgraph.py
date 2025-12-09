import json
from google.genai import types
from app.services import network_service

definitions = [
    types.FunctionDeclaration(
        name="create_ego_network",
        description="Create an ego network subgraph centered on a specific node.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "center_node_id": types.Schema(type="STRING", description="ID of the center node."),
                "radius": types.Schema(type="INTEGER", description="Radius of the ego network (default 1).")
            },
            required=["center_node_id"]
        )
    ),
    types.FunctionDeclaration(
        name="create_subgraph_from_nodes",
        description="Create a subgraph containing only the specified nodes.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "node_ids": types.Schema(
                    type="ARRAY",
                    items=types.Schema(type="STRING"),
                    description="List of node IDs to include."
                )
            },
            required=["node_ids"]
        )
    ),
    types.FunctionDeclaration(
        name="create_path_subgraph",
        description="Create a subgraph containing the shortest path between two nodes.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "source_node_id": types.Schema(type="STRING", description="Start node ID."),
                "target_node_id": types.Schema(type="STRING", description="End node ID.")
            },
            required=["source_node_id", "target_node_id"]
        )
    ),
    types.FunctionDeclaration(
        name="create_k_core_subgraph",
        description="Create a k-core subgraph (maximal subgraph where every node has degree >= k).",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "k": types.Schema(type="INTEGER", description="The core number k.")
            },
            required=["k"]
        )
    ),
    types.FunctionDeclaration(
        name="create_largest_component_subgraph",
        description="Create a subgraph from the largest connected component.",
        parameters=types.Schema(type="OBJECT", properties={})
    ),
    types.FunctionDeclaration(
        name="get_subgraphs",
        description="List all available subgraphs for the current network.",
        parameters=types.Schema(type="OBJECT", properties={})
    )
]

async def create_ego_network(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    center_node_id = args.get("center_node_id")
    radius = args.get("radius", 1)
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating ego network for {center_node_id}..."})})
    result = await network_service.create_ego_network(network_id, center_node_id, radius)
    
    # Auto-switch context
    db = context['db']
    chat_id = context['chat_id']
    from app import models
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if chat:
        chat.network_id = result['new_network_id']
        db.commit()

    return {"status": "success", "message": f"Created ego network: {result['name']}. Switched focus to this subgraph.", "subgraph_id": result['new_network_id']}

async def create_subgraph_from_nodes(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    node_ids = args.get("node_ids")
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating subgraph from {len(node_ids)} nodes..."})})
    result = await network_service.create_subgraph_from_nodes(network_id, node_ids)

    # Auto-switch context
    db = context['db']
    chat_id = context['chat_id']
    from app import models
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if chat:
        chat.network_id = result['new_network_id']
        db.commit()

    return {"status": "success", "message": f"Created subgraph: {result['name']}. Switched focus to this subgraph.", "subgraph_id": result['new_network_id']}

async def create_path_subgraph(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    source_node_id = args.get("source_node_id")
    target_node_id = args.get("target_node_id")
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating path subgraph from {source_node_id} to {target_node_id}..."})})
    result = await network_service.create_path_subgraph(network_id, source_node_id, target_node_id)

    # Auto-switch context
    db = context['db']
    chat_id = context['chat_id']
    from app import models
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if chat:
        chat.network_id = result['new_network_id']
        db.commit()

    return {"status": "success", "message": f"Created path subgraph: {result['name']}. Switched focus to this subgraph.", "subgraph_id": result['new_network_id']}

async def create_k_core_subgraph(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    k = args.get("k")
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating {k}-core subgraph..."})})
    result = await network_service.create_k_core_subgraph(network_id, k)

    # Auto-switch context
    db = context['db']
    chat_id = context['chat_id']
    from app import models
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if chat:
        chat.network_id = result['new_network_id']
        db.commit()

    return {"status": "success", "message": f"Created k-core subgraph: {result['name']}. Switched focus to this subgraph.", "subgraph_id": result['new_network_id']}

async def create_largest_component_subgraph(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating largest component subgraph..."})})
    result = await network_service.create_largest_component_subgraph(network_id)
    
    # Auto-switch context
    db = context['db']
    chat_id = context['chat_id']
    from app import models # Lazy import to avoid circular dep if any
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if chat:
        chat.network_id = result['new_network_id']
        db.commit()

    return {"status": "success", "message": f"Created largest component subgraph: {result['name']}. Switched focus to this subgraph.", "subgraph_id": result['new_network_id']}

async def get_subgraphs(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    result = await network_service.get_subgraphs(network_id)
    return {"subgraphs": result}

handlers = {
    "create_ego_network": create_ego_network,
    "create_subgraph_from_nodes": create_subgraph_from_nodes,
    "create_path_subgraph": create_path_subgraph,
    "create_k_core_subgraph": create_k_core_subgraph,
    "create_largest_component_subgraph": create_largest_component_subgraph,
    "get_subgraphs": get_subgraphs
}
