"""
Layout calculation and persistence tools module
==============================================

Provides layout calculation tools that integrate with the new MCP architecture.
Supports two-stage process (calculation and rendering) with persistent storage.
"""

import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    from mcp.server.fastmcp import FastMCP, Context
    from mcp.server.session import ServerSession
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

    class FastMCP:
        def tool(self):
            def decorator(func):
                return func
            return decorator

    class Context:
        pass

    class ServerSession:
        pass

from core.context import ServerContext
from core.graph_utils import parse_graphml_content

logger = logging.getLogger("networkx_mcp.tools.layout_persistence")

# Layout calculation results cache
layout_cache = {}


class LayoutCalculationResult:
    """Layout calculation result container"""

    def __init__(self, layout_type: str, positions: Dict[str, Dict[str, float]],
                 layout_params: Dict[str, Any] = None, metadata: Dict[str, Any] = None):
        self.layout_type = layout_type
        self.positions = positions
        self.layout_params = layout_params or {}
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        self.calculation_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "layout_type": self.layout_type,
            "positions": self.positions,
            "layout_params": self.layout_params,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "calculation_id": self.calculation_id
        }


def get_networkx_graph_from_context(context: ServerContext) -> Optional[nx.Graph]:
    """Get NetworkX graph from server context"""
    if not NETWORKX_AVAILABLE:
        logger.error("NetworkX is not available")
        return None

    try:
        graphml_content = getattr(context, 'graphml_content', None)
        if not graphml_content:
            logger.warning("No GraphML content found in context")
            return None

        return parse_graphml_content(graphml_content)
    except Exception as e:
        logger.error(f"Error parsing GraphML content: {e}")
        return None


def calculate_layout_positions(graph: nx.Graph, layout_type: str, layout_params: Dict[str, Any] = None) -> Dict[str, Dict[str, float]]:
    """Calculate layout positions using NetworkX algorithms"""
    if not graph:
        raise ValueError("Graph is required for layout calculation")

    layout_params = layout_params or {}

    # Available NetworkX layout algorithms
    layout_functions = {
        'spring': nx.spring_layout,
        'kamada_kawai': nx.kamada_kawai_layout,
        'circular': nx.circular_layout,
        'random': nx.random_layout,
        'shell': nx.shell_layout,
        'spectral': nx.spectral_layout,
        'planar': nx.planar_layout,
        'spiral': nx.spiral_layout,
        'bipartite': nx.bipartite_layout,
        'multipartite': nx.multipartite_layout
    }

    if layout_type not in layout_functions:
        raise ValueError(
            f"Unsupported layout type: {layout_type}. Available: {list(layout_functions.keys())}")

    layout_func = layout_functions[layout_type]

    try:
        # Apply layout function with parameters
        if layout_type == 'spring':
            # Spring layout specific parameters
            pos = layout_func(
                graph,
                k=layout_params.get('k', None),
                pos=layout_params.get('pos', None),
                fixed=layout_params.get('fixed', None),
                iterations=layout_params.get('iterations', 50),
                threshold=layout_params.get('threshold', 1e-4),
                weight=layout_params.get('weight', 'weight'),
                scale=layout_params.get('scale', 1),
                center=layout_params.get('center', None),
                dim=layout_params.get('dim', 2),
                seed=layout_params.get('seed', None)
            )
        elif layout_type == 'kamada_kawai':
            pos = layout_func(
                graph,
                dist=layout_params.get('dist', None),
                pos=layout_params.get('pos', None),
                weight=layout_params.get('weight', 'weight'),
                scale=layout_params.get('scale', 1),
                center=layout_params.get('center', None),
                dim=layout_params.get('dim', 2)
            )
        elif layout_type == 'circular':
            pos = layout_func(
                graph,
                scale=layout_params.get('scale', 1),
                center=layout_params.get('center', None),
                dim=layout_params.get('dim', 2)
            )
        elif layout_type == 'random':
            pos = layout_func(
                graph,
                center=layout_params.get('center', None),
                dim=layout_params.get('dim', 2),
                seed=layout_params.get('seed', None)
            )
        elif layout_type == 'shell':
            pos = layout_func(
                graph,
                nlist=layout_params.get('nlist', None),
                rotate=layout_params.get('rotate', None),
                scale=layout_params.get('scale', 1),
                center=layout_params.get('center', None),
                dim=layout_params.get('dim', 2)
            )
        elif layout_type == 'spectral':
            pos = layout_func(
                graph,
                weight=layout_params.get('weight', 'weight'),
                scale=layout_params.get('scale', 1),
                center=layout_params.get('center', None),
                dim=layout_params.get('dim', 2)
            )
        elif layout_type == 'bipartite':
            # Bipartite layout requires nodes parameter
            nodes = layout_params.get('nodes', None)
            if not nodes and nx.is_bipartite(graph):
                # Auto-detect bipartite sets
                nodes = set(n for n, d in graph.nodes(data=True)
                            if d.get('bipartite', 0) == 0)
            pos = layout_func(
                graph,
                nodes,
                align=layout_params.get('align', 'vertical'),
                scale=layout_params.get('scale', 1),
                center=layout_params.get('center', None),
                aspect_ratio=layout_params.get('aspect_ratio', 4/3)
            )
        else:
            # For other layouts, use basic parameters
            filtered_params = {k: v for k, v in layout_params.items()
                               if k in ['scale', 'center', 'dim']}
            pos = layout_func(graph, **filtered_params)

        # Convert numpy arrays to regular floats for JSON serialization
        positions = {}
        for node_id, (x, y) in pos.items():
            positions[str(node_id)] = {
                'x': float(x),
                'y': float(y)
            }

        return positions

    except Exception as e:
        logger.error(f"Error calculating {layout_type} layout: {e}")
        raise


# FastMCP tools
app = FastMCP("NetworkX Layout Tools")


@app.tool()
def calculate_and_store_layout(
    layout_type: str,
    layout_params: dict = None
) -> dict:
    """
    🔄 Calculate and store layout positions (Stage 1 of 2).

    Calculate layout positions using NetworkX algorithms and store them for visualization.
    This is the first stage of the two-stage layout process.

    Args:
        layout_type: Type of layout algorithm to use
        layout_params: Optional parameters for the layout algorithm

    Returns:
        Dictionary with calculation results and metadata
    """
    if not NETWORKX_AVAILABLE:
        return {
            "success": False,
            "error": "NetworkX is not available",
            "message": "❌ NetworkX library is required for layout calculations"
        }

    try:
        # Get graph from context
        context = ServerContext.get_instance()
        graph = get_networkx_graph_from_context(context)

        if not graph:
            return {
                "success": False,
                "error": "No graph data available",
                "message": "❌ No graph data found. Please upload a network file first."
            }

        # Calculate layout positions
        positions = calculate_layout_positions(
            graph, layout_type, layout_params)

        # Create result object
        result = LayoutCalculationResult(
            layout_type=layout_type,
            positions=positions,
            layout_params=layout_params,
            metadata={
                "node_count": len(positions),
                "edge_count": graph.number_of_edges(),
                "graph_info": {
                    "nodes": graph.number_of_nodes(),
                    "edges": graph.number_of_edges(),
                    "is_directed": graph.is_directed(),
                    "density": nx.density(graph)
                }
            }
        )

        # Store in cache
        layout_cache[result.calculation_id] = result

        logger.info(
            f"Layout calculation completed: {layout_type} for {len(positions)} nodes")

        return {
            "success": True,
            "calculation_id": result.calculation_id,
            "layout_type": layout_type,
            "node_count": len(positions),
            "message": f"✅ {layout_type.title()} layout calculation completed! Calculated positions for {len(positions)} nodes.",
            "positions_sample": dict(list(positions.items())[:3]) if positions else {},
            "next_step": "Use get_layout_visualization_data to retrieve the complete layout data for rendering"
        }

    except Exception as e:
        logger.error(f"Error in calculate_and_store_layout: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"❌ Layout calculation failed: {str(e)}"
        }


@app.tool()
def get_layout_visualization_data(calculation_id: str) -> dict:
    """
    📊 Get layout visualization data (Stage 2 of 2).

    Retrieve the complete layout calculation results for visualization.
    This is the second stage of the two-stage layout process.

    Args:
        calculation_id: ID of the layout calculation from stage 1

    Returns:
        Complete layout data ready for Cytoscape.js visualization
    """
    try:
        if calculation_id not in layout_cache:
            return {
                "success": False,
                "error": "Calculation not found",
                "message": f"❌ Layout calculation {calculation_id} not found. Please run calculate_and_store_layout first."
            }

        result = layout_cache[calculation_id]

        # Get graph from context for edge data
        context = ServerContext.get_instance()
        graph = get_networkx_graph_from_context(context)

        # Prepare Cytoscape.js format data
        cytoscape_elements = []

        # Add nodes with positions
        for node_id, position in result.positions.items():
            cytoscape_elements.append({
                "group": "nodes",
                "data": {
                    "id": str(node_id),
                    "label": str(node_id)
                },
                "position": {
                    "x": position['x'],
                    "y": position['y']
                }
            })

        # Add edges if graph is available
        if graph:
            for source, target in graph.edges():
                cytoscape_elements.append({
                    "group": "edges",
                    "data": {
                        "id": f"{source}-{target}",
                        "source": str(source),
                        "target": str(target)
                    }
                })

        visualization_data = {
            "elements": cytoscape_elements,
            "layout": {
                "name": "preset"  # Use preset since we have calculated positions
            },
            "style": [
                {
                    "selector": "node",
                    "style": {
                        "background-color": "#666",
                        "label": "data(label)",
                        "text-valign": "center",
                        "color": "white",
                        "text-outline-width": 2,
                        "text-outline-color": "#666",
                        "font-size": "12px"
                    }
                },
                {
                    "selector": "edge",
                    "style": {
                        "width": 2,
                        "line-color": "#ccc",
                        "target-arrow-color": "#ccc",
                        "target-arrow-shape": "triangle",
                        "curve-style": "bezier"
                    }
                }
            ],
            "metadata": result.metadata
        }

        logger.info(
            f"Layout visualization data prepared for {len(cytoscape_elements)} elements")

        return {
            "success": True,
            "calculation_id": calculation_id,
            "layout_type": result.layout_type,
            "visualization_data": visualization_data,
            "message": f"✅ {result.layout_type.title()} layout visualization data ready! Generated {len(cytoscape_elements)} elements for Cytoscape.js rendering."
        }

    except Exception as e:
        logger.error(f"Error in get_layout_visualization_data: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"❌ Failed to prepare visualization data: {str(e)}"
        }


@app.tool()
def list_available_layouts() -> dict:
    """
    📋 List all available layout algorithms.

    Returns a list of all supported NetworkX layout algorithms with descriptions.

    Returns:
        Dictionary containing available layout types and their descriptions
    """
    if not NETWORKX_AVAILABLE:
        return {
            "success": False,
            "error": "NetworkX is not available",
            "message": "❌ NetworkX library is required"
        }

    layouts = {
        "spring": {
            "name": "Spring Layout",
            "description": "Force-directed layout using Fruchterman-Reingold algorithm",
            "parameters": ["k", "iterations", "threshold", "scale", "center", "dim", "seed"],
            "best_for": "General purpose, good for most networks"
        },
        "kamada_kawai": {
            "name": "Kamada-Kawai Layout",
            "description": "Spring-model layout with global optimization",
            "parameters": ["dist", "weight", "scale", "center", "dim"],
            "best_for": "High-quality layouts, good for small to medium networks"
        },
        "circular": {
            "name": "Circular Layout",
            "description": "Position nodes in a circle",
            "parameters": ["scale", "center", "dim"],
            "best_for": "Highlighting network structure, cycle detection"
        },
        "random": {
            "name": "Random Layout",
            "description": "Position nodes randomly",
            "parameters": ["center", "dim", "seed"],
            "best_for": "Initial positioning, testing"
        },
        "shell": {
            "name": "Shell Layout",
            "description": "Position nodes in concentric circles",
            "parameters": ["nlist", "rotate", "scale", "center", "dim"],
            "best_for": "Hierarchical networks, core-periphery structures"
        },
        "spectral": {
            "name": "Spectral Layout",
            "description": "Position nodes using eigenvectors of the graph Laplacian",
            "parameters": ["weight", "scale", "center", "dim"],
            "best_for": "Community detection, clustering visualization"
        },
        "planar": {
            "name": "Planar Layout",
            "description": "Position nodes for planar graphs without edge crossings",
            "parameters": ["scale", "center"],
            "best_for": "Planar graphs, tree structures"
        },
        "spiral": {
            "name": "Spiral Layout",
            "description": "Position nodes in a spiral pattern",
            "parameters": ["scale", "center", "dim"],
            "best_for": "Time series networks, sequential data"
        },
        "bipartite": {
            "name": "Bipartite Layout",
            "description": "Position nodes in two columns for bipartite graphs",
            "parameters": ["nodes", "align", "scale", "center", "aspect_ratio"],
            "best_for": "Bipartite graphs, two-mode networks"
        },
        "multipartite": {
            "name": "Multipartite Layout",
            "description": "Position nodes in multiple layers",
            "parameters": ["subset_key", "align", "scale", "center"],
            "best_for": "Multilayer networks, hierarchical structures"
        }
    }

    return {
        "success": True,
        "layouts": layouts,
        "message": f"📋 {len(layouts)} layout algorithms available",
        "total_count": len(layouts)
    }


@app.tool()
def get_layout_parameters_info(layout_type: str) -> dict:
    """
    ℹ️ Get detailed parameter information for a specific layout algorithm.

    Args:
        layout_type: The layout algorithm to get parameter info for

    Returns:
        Detailed parameter information for the specified layout
    """
    parameter_info = {
        "spring": {
            "k": "Optimal distance between nodes (float or None)",
            "iterations": "Maximum number of iterations (int, default: 50)",
            "threshold": "Threshold for relative error (float, default: 1e-4)",
            "scale": "Scale factor for positions (float, default: 1)",
            "center": "Coordinate pair for center position (tuple or None)",
            "dim": "Dimension of layout (int, default: 2)",
            "seed": "Random seed for reproducible layouts (int or None)"
        },
        "kamada_kawai": {
            "dist": "Distance matrix between nodes (dict or None)",
            "weight": "Edge attribute for distance (string, default: 'weight')",
            "scale": "Scale factor for positions (float, default: 1)",
            "center": "Coordinate pair for center position (tuple or None)",
            "dim": "Dimension of layout (int, default: 2)"
        },
        "circular": {
            "scale": "Scale factor for positions (float, default: 1)",
            "center": "Coordinate pair for center position (tuple or None)",
            "dim": "Dimension of layout (int, default: 2)"
        },
        "random": {
            "center": "Coordinate pair for center position (tuple or None)",
            "dim": "Dimension of layout (int, default: 2)",
            "seed": "Random seed for reproducible layouts (int or None)"
        },
        "shell": {
            "nlist": "List of lists for shell arrangement (list or None)",
            "rotate": "Rotate the layout (float or None)",
            "scale": "Scale factor for positions (float, default: 1)",
            "center": "Coordinate pair for center position (tuple or None)",
            "dim": "Dimension of layout (int, default: 2)"
        },
        "spectral": {
            "weight": "Edge attribute for weights (string, default: 'weight')",
            "scale": "Scale factor for positions (float, default: 1)",
            "center": "Coordinate pair for center position (tuple or None)",
            "dim": "Dimension of layout (int, default: 2)"
        },
        "bipartite": {
            "nodes": "Nodes in one bipartite set (list or None)",
            "align": "Alignment of layout ('vertical' or 'horizontal')",
            "scale": "Scale factor for positions (float, default: 1)",
            "center": "Coordinate pair for center position (tuple or None)",
            "aspect_ratio": "Ratio of width to height (float, default: 4/3)"
        }
    }

    if layout_type not in parameter_info:
        return {
            "success": False,
            "error": f"Unknown layout type: {layout_type}",
            "message": f"❌ Layout type '{layout_type}' not found. Use list_available_layouts to see available options."
        }

    return {
        "success": True,
        "layout_type": layout_type,
        "parameters": parameter_info[layout_type],
        "message": f"ℹ️ Parameter information for {layout_type} layout",
        "parameter_count": len(parameter_info[layout_type])
    }


if __name__ == "__main__":
    # For testing
    app.run()
