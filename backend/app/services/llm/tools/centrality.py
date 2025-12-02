import json
from google.genai import types
from app.services import network_service

definitions = [
    types.FunctionDeclaration(
        name="calculate_centrality",
        description="Calculate centrality metrics to identify important nodes.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "centrality_type": types.Schema(
                    type="STRING",
                    description="Type of centrality. Options: degree, betweenness, closeness, eigenvector",
                    enum=["degree", "betweenness", "closeness", "eigenvector"]
                )
            },
            required=["centrality_type"]
        )
    ),
    types.FunctionDeclaration(
        name="get_top_nodes",
        description="Get the top k nodes based on a centrality metric. Useful for identifying key nodes to focus on.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "metric": types.Schema(
                    type="STRING",
                    description="Centrality metric to use. Options: degree, betweenness, closeness, eigenvector",
                    enum=["degree", "betweenness", "closeness", "eigenvector"]
                ),
                "k": types.Schema(type="INTEGER", description="Number of top nodes to return (default 10).")
            },
            required=["metric"]
        )
    )
]

async def calculate_centrality(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    centrality_type = args.get("centrality_type", "degree")
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Calculating {centrality_type} centrality..."})})
    await network_service.calculate_centrality(network_id, centrality_type)
    return {"status": "success", "message": f"Calculated {centrality_type} centrality."}

async def get_top_nodes(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    metric = args.get("metric")
    k = args.get("k", 10)
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Finding top {k} nodes by {metric} centrality..."})})
    result = await network_service.get_top_nodes(network_id, metric, k)
    return {"top_nodes": result}

handlers = {
    "calculate_centrality": calculate_centrality,
    "get_top_nodes": get_top_nodes
}
