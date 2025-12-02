import json
from google.genai import types
from app.services import network_service

definitions = [
    types.FunctionDeclaration(
        name="generate_visualization",
        description="Create the visualization with specific layout, size, and color settings.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "layout_name": types.Schema(
                    type="STRING",
                    description="Name of the layout algorithm.",
                    enum=["spring", "circular", "kamada_kawai", "shell", "spectral"]
                ),
                "node_size_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for node sizes. WARNING: The attribute MUST exist. Call calculate_centrality first if needed.",
                    properties={
                        "attribute": types.Schema(type="STRING", description="Name of the attribute (e.g., 'degree_centrality'). MUST be calculated first."),
                        "min": types.Schema(type="NUMBER"),
                        "max": types.Schema(type="NUMBER")
                    }
                ),
                "node_color_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for node colors.",
                    properties={
                        "attribute": types.Schema(type="STRING"),
                        "scale_type": types.Schema(type="STRING", description="LINEAR, CATEGORICAL, or RANKING"),
                        "ranking_rules": types.Schema(
                            type="ARRAY",
                            description="Rules for RANKING scale_type. Processed in order. e.g. [{'top': 1, 'color': 'red'}, {'top': 5, 'color': 'blue'}] means top 1 is red, next 5 are blue.",
                            items=types.Schema(
                                type="OBJECT",
                                properties={
                                    "top": types.Schema(type="INTEGER", description="Number of nodes to apply this color to (taking from the top of the remaining list)."),
                                    "color": types.Schema(type="STRING", description="Color for these nodes.")
                                }
                            )
                        ),
                        "default_color": types.Schema(type="STRING", description="Color for nodes not matching any rule.")
                    }
                ),
                "edge_width_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for edge widths.",
                    properties={
                        "attribute": types.Schema(type="STRING"),
                        "min": types.Schema(type="NUMBER"),
                        "max": types.Schema(type="NUMBER")
                    }
                ),
                "edge_color_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for edge colors.",
                    properties={
                        "attribute": types.Schema(type="STRING"),
                        "scale_type": types.Schema(type="STRING")
                    }
                ),
                "overlay_network_id": types.Schema(
                    type="INTEGER",
                    description="ID of a subgraph to overlay/highlight on the main visualization."
                ),
                "overlay_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for overlay colors.",
                    properties={
                        "highlight_color": types.Schema(type="STRING", description="Color for the highlighted subgraph nodes/edges (default: #FF4500)."),
                        "dimmed_color": types.Schema(type="STRING", description="Color for the non-highlighted nodes/edges (default: #B0B0B0).")
                    }
                ),
                "custom_node_colors": types.Schema(
                    type="ARRAY",
                    description="List of specific node-color pairs. Overrides all other color settings for these nodes. Useful for highlighting specific nodes identified by the LLM.",
                    items=types.Schema(
                        type="OBJECT",
                        properties={
                            "node_id": types.Schema(type="STRING"),
                            "color": types.Schema(type="STRING")
                        },
                        required=["node_id", "color"]
                    )
                )
            },
            required=["layout_name"]
        )
    )
]

async def generate_visualization(args: dict, context: dict) -> dict:
    network_id = context['network_id']
    queue = context['queue']
    
    vis_config = {
        "layout_name": args.get("layout_name", "spring"),
        "node_size_config": args.get("node_size_config"),
        "node_color_config": args.get("node_color_config"),
        "edge_width_config": args.get("edge_width_config"),
        "edge_color_config": args.get("edge_color_config"),
        "overlay_network_id": args.get("overlay_network_id"),
        "overlay_config": args.get("overlay_config"),
        "custom_node_colors": args.get("custom_node_colors")
    }
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Creating visualization..."})})
    vis_data = await network_service.generate_visualization(network_id, vis_config)
    
    await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
    return {"status": "success", "message": "Visualization created."}

handlers = {
    "generate_visualization": generate_visualization
}
