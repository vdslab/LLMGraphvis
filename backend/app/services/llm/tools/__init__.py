from typing import List, Dict, Callable, Any
from google.genai import types
from . import attributes, centrality, visualization, layout, subgraph

def get_definitions() -> List[types.FunctionDeclaration]:
    """Aggregate all tool definitions."""
    definitions = []
    definitions.extend(attributes.definitions)
    definitions.extend(centrality.definitions)
    definitions.extend(visualization.definitions)
    definitions.extend(layout.definitions)
    definitions.extend(subgraph.definitions)
    return definitions

def get_handlers() -> Dict[str, Callable]:
    """Aggregate all tool handlers."""
    handlers = {}
    handlers.update(attributes.handlers)
    handlers.update(centrality.handlers)
    handlers.update(visualization.handlers)
    handlers.update(layout.handlers)
    handlers.update(subgraph.handlers)
    return handlers

async def execute_tool(function_name: str, function_args: dict, context: dict) -> dict:
    """Execute a tool by name."""
    handlers = get_handlers()
    if function_name not in handlers:
        raise ValueError(f"Unknown function: {function_name}")
    
    handler = handlers[function_name]
    return await handler(function_args, context)
