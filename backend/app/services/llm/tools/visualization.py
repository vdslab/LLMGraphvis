import json
from google.genai import types
from app.services import network_service

definitions = [
    types.FunctionDeclaration(
        name="generate_visualization",
        description="Generates visualization data (nodes, links, positions, styles) for a network. Supports 'Focus + Context' visualization where a specific subgraph (focus_network_id) can be highlighted or styled differently from the main network (network_id).",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "network_id": types.Schema(
                    type="INTEGER",
                    description="The ID of the main network to visualize (provides the global layout and context)."
                ),
                "layout_name": types.Schema(
                    type="STRING",
                    description="Name of the layout algorithm to use (e.g., 'spring', 'circular'). Defaults to 'spring'.",
                    enum=["spring", "circular", "kamada_kawai", "shell", "spectral"]
                ),
                "node_size_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for global node sizing based on attributes.",
                    properties={
                        "attribute": types.Schema(type="STRING", description="Name of the attribute to map to size."),
                        "min": types.Schema(type="NUMBER", description="Minimum node size."),
                        "max": types.Schema(type="NUMBER", description="Maximum node size.")
                    },
                    required=["attribute"]
                ),
                "node_color_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for global node coloring based on attributes.",
                    properties={
                        "attribute": types.Schema(type="STRING", description="Name of the attribute to map to color."),
                        "scale_type": types.Schema(type="STRING", enum=["LINEAR", "CATEGORICAL", "RANKING"], description="Type of color scale."),
                        "gradient": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="List of two colors for linear gradient (min, max)."),
                        "color_map": types.Schema(type="OBJECT", description="Map of values to colors for categorical scale."),
                        "ranking_rules": types.Schema(
                            type="ARRAY",
                            items=types.Schema(
                                type="OBJECT",
                                properties={
                                    "top": types.Schema(type="INTEGER"),
                                    "color": types.Schema(type="STRING")
                                }
                            ),
                            description="Rules for RANKING scale (e.g., top 3 red)."
                        ),
                        "default_color": types.Schema(type="STRING", description="Fallback color.")
                    },
                    required=["attribute"]
                ),
                "edge_width_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for global edge width.",
                    properties={
                        "attribute": types.Schema(type="STRING"),
                        "min": types.Schema(type="NUMBER"),
                        "max": types.Schema(type="NUMBER")
                    },
                    required=["attribute"]
                ),
                "edge_color_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for global edge color.",
                    properties={
                        "attribute": types.Schema(type="STRING"),
                        "scale_type": types.Schema(type="STRING", enum=["LINEAR", "CATEGORICAL"]),
                        "gradient": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                        "color_map": types.Schema(type="OBJECT")
                    },
                    required=["attribute"]
                ),
                "focus_network_id": types.Schema(
                    type="INTEGER",
                    description="ID of a subgraph to focus on. Nodes in this subgraph will be highlighted or styled according to focus_config."
                ),
                "context_config": types.Schema(
                    type="OBJECT",
                    description="Configuration for the 'context' (nodes NOT in focus_network_id).",
                    properties={
                        "opacity": types.Schema(type="NUMBER", description="Opacity of context nodes (0.0 - 1.0). Default 0.1."),
                        "color": types.Schema(type="STRING", description="Color of context nodes. Default light gray."),
                        "visible": types.Schema(type="BOOLEAN", description="Whether to show context nodes. Default true.")
                    }
                ),
                "focus_config": types.Schema(
                    type="OBJECT",
                    description="Configuration specifically for the 'focus' nodes. Overrides global configs.",
                    properties={
                        "node_size_config": types.Schema(
                            type="OBJECT",
                            description="Size config using attributes from the SUBGRAPH (focus_network_id).",
                            properties={
                                "attribute": types.Schema(type="STRING"),
                                "min": types.Schema(type="NUMBER"),
                                "max": types.Schema(type="NUMBER")
                            }
                        ),
                        "node_color_config": types.Schema(
                            type="OBJECT",
                            description="Color config using attributes from the SUBGRAPH.",
                            properties={
                                "attribute": types.Schema(type="STRING"),
                                "scale_type": types.Schema(type="STRING"),
                                "static_color": types.Schema(type="STRING", description="Fixed color for all focus nodes.")
                            }
                        )
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
        # Support both new and old parameter names for robustness
        "focus_network_id": args.get("focus_network_id") or args.get("overlay_network_id"),
        "context_config": args.get("context_config") or args.get("overlay_config"), # Simple fallback, though structures might differ slightly
        "focus_config": args.get("focus_config"),
        "custom_node_colors": args.get("custom_node_colors")
    }

    # Robustness: If focus_network_id is set but context_config is missing, apply default dimming.
    if vis_config["focus_network_id"] and not vis_config["context_config"]:
        vis_config["context_config"] = {"opacity": 0.1}
    
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Creating visualization..."})})
    vis_data = await network_service.generate_visualization(network_id, vis_config)
    
    await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
    return {"status": "success", "message": "Visualization created."}

handlers = {
    "generate_visualization": generate_visualization
}
