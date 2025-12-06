import json
from google.genai import types
from app.services import network_service

definitions = [
    types.FunctionDeclaration(
        name="calculate_layout",
        description="Calculate and save a specific layout algorithm to arrange the nodes.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "network_id": types.Schema(
                    type="INTEGER",
                    description="Optional ID of the network/subgraph to calculate for. Defaults to the current active network."
                ),
                "layout_name": types.Schema(
                    type="STRING",
                    description="Name of the layout algorithm.",
                    enum=["spring", "circular", "kamada_kawai", "shell", "spectral"]
                )
            },
            required=["layout_name"]
        )
    )
]

async def calculate_layout(args: dict, context: dict) -> dict:
    network_id = args.get("network_id", context['network_id'])
    queue = context['queue']
    layout_name = args.get("layout_name", "spring")
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Calculating {layout_name} layout for network {network_id}..."})})
    await network_service.calculate_layout(network_id, layout_name)
    return {"status": "success", "message": f"Calculated {layout_name} layout."}

handlers = {
    "calculate_layout": calculate_layout
}
