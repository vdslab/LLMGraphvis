"""
NetworkX MCP Server - FastAPI Integration
=========================================

FastAPI-based Model Context Protocol server for NetworkX graph analysis.
Follows MCP best practices while maintaining FastAPI compatibility.
"""

import os
import logging
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure MCP-compliant logging (stderr, not stdout)
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr  # MCP requirement: use stderr for logging
)
logger = logging.getLogger("networkx_mcp")

# FastAPI app setup
app = FastAPI(
    title="NetworkX MCP Server",
    description="FastAPI-based MCP server for network analysis and visualization using NetworkX",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try to integrate FastMCP if available
try:
    from fastapi_mcp import FastApiMCP
    mcp = FastApiMCP(app)
    mcp.mount()  # Mount MCP server at /mcp
    logger.info("FastAPI-MCP integration enabled")
    MCP_AVAILABLE = True
except ImportError:
    logger.warning("FastAPI-MCP not available, running FastAPI-only mode")
    MCP_AVAILABLE = False

# Shared context for caching (MCP-style but FastAPI compatible)


class ServerContext:
    """Shared server context for caching and state management."""

    def __init__(self):
        self.graph_cache: Dict[str, Any] = {}
        self.centrality_cache: Dict[str, Any] = {}
        self.calculation_history: Dict[str, Any] = {}

    def clear_caches(self) -> None:
        """Clear all caches."""
        self.graph_cache.clear()
        self.centrality_cache.clear()
        self.calculation_history.clear()
        logger.info("All caches cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "graphs": len(self.graph_cache),
            "centrality_calculations": len(self.centrality_cache),
            "calculation_history": len(self.calculation_history)
        }


# Global context instance
server_context = ServerContext()

# --- Pydantic Models (MCP-style structured data) ---


class GraphMLRequest(BaseModel):
    """Base model for GraphML content requests."""
    graphml_content: str = Field(..., description="GraphML content as string")


class NetworkCreationRequest(BaseModel):
    """Request model for network creation."""
    network_type: str = Field(
        "random", description="Type of network to create")
    num_nodes: int = Field(20, description="Number of nodes")
    edge_probability: float = Field(
        0.2, description="Edge probability for random networks")
    seed: Optional[int] = Field(
        None, description="Random seed for reproducibility")


class LayoutRequest(GraphMLRequest):
    """Request model for layout algorithms."""
    layout_type: str = Field("spring", description="Layout algorithm type")
    layout_params: Dict[str, Any] = Field(
        default_factory=dict, description="Layout parameters")


class CentralityRequest(GraphMLRequest):
    """Request model for centrality calculations."""
    centrality_type: str = Field("degree", description="Centrality type")
    centrality_params: Dict[str, Any] = Field(
        default_factory=dict, description="Centrality parameters")


class VisualizationRequest(BaseModel):
    """Request model for visualization data."""
    graph_id: Optional[str] = Field(None, description="Cached graph ID")
    graphml_content: Optional[str] = Field(None, description="GraphML content")
    metric_values: Optional[Dict[str, float]] = Field(
        None, description="Metric values for styling")
    color_scheme: str = Field("viridis", description="Color scheme")
    size_range: List[float] = Field([5, 20], description="Node size range")

# --- MCP-style Response Models ---


class MCPResponse(BaseModel):
    """Standard MCP response format."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

# --- Core API Endpoints (MCP-compatible) ---


@app.get("/", response_model=MCPResponse)
async def root():
    """Root endpoint with server information."""
    return MCPResponse(
        success=True,
        data={
            "name": "NetworkX MCP Server",
            "version": "1.0.0",
            "description": "FastAPI-based MCP server for network analysis",
            "mcp_enabled": MCP_AVAILABLE,
            "endpoints": {
                "health": "/health",
                "mcp": "/mcp" if MCP_AVAILABLE else None,
                "tools": "/tools/",
                "resources": "/resources/",
                "cache": "/cache/"
            }
        }
    )


@app.get("/health", response_model=MCPResponse)
async def health_check():
    """Health check endpoint."""
    return MCPResponse(
        success=True,
        data={
            "status": "healthy",
            "cache_stats": server_context.get_cache_stats(),
            "mcp_available": MCP_AVAILABLE
        }
    )

# --- MCP Resource-style Endpoints ---


@app.get("/resources/graphs", response_model=MCPResponse)
async def list_cached_graphs():
    """List all cached graphs (MCP resource style)."""
    try:
        graphs_list = []
        for graph_id, graph_data in server_context.graph_cache.items():
            graphs_list.append({
                "graph_id": graph_id,
                "nodes": graph_data.get("nodes", 0),
                "edges": graph_data.get("edges", 0),
                "created_at": graph_data.get("created_at"),
                "layout_type": graph_data.get("layout_type"),
                "metrics_count": len(graph_data.get("metrics", {}))
            })

        return MCPResponse(
            success=True,
            data={
                "cached_graphs": graphs_list,
                "total_count": len(graphs_list)
            }
        )
    except Exception as e:
        logger.error(f"Error listing graphs: {e}")
        return MCPResponse(success=False, error=str(e))


@app.get("/resources/graphs/{graph_id}", response_model=MCPResponse)
async def get_cached_graph(graph_id: str):
    """Get a specific cached graph."""
    try:
        if graph_id not in server_context.graph_cache:
            raise HTTPException(
                status_code=404, detail=f"Graph {graph_id} not found")

        graph_data = server_context.graph_cache[graph_id]
        return MCPResponse(
            success=True,
            data={
                "graph_id": graph_id,
                "metadata": graph_data.get("metadata", {}),
                "graphml_content": graph_data.get("graphml_content", ""),
                "available_metrics": list(graph_data.get("metrics", {}).keys())
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting graph {graph_id}: {e}")
        return MCPResponse(success=False, error=str(e))


@app.get("/resources/cache/stats", response_model=MCPResponse)
async def get_cache_statistics():
    """Get cache statistics (MCP resource style)."""
    try:
        stats = server_context.get_cache_stats()
        detailed_stats = {
            "basic_stats": stats,
            "graph_cache": {
                "total_graphs": len(server_context.graph_cache),
                "graph_ids": list(server_context.graph_cache.keys())
            },
            "centrality_cache": {
                "total_calculations": len(server_context.centrality_cache),
                "calculation_ids": list(server_context.centrality_cache.keys())
            }
        }

        return MCPResponse(success=True, data=detailed_stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return MCPResponse(success=False, error=str(e))

# --- MCP Tool-style Endpoints ---


@app.post("/tools/create_network", response_model=MCPResponse)
async def create_network_tool(request: NetworkCreationRequest):
    """Create a network (MCP tool style)."""
    try:
        # Import and use the modular network tools
        from tools.network_operations import create_sample_network

        result = create_sample_network(
            network_type=request.network_type,
            num_nodes=request.num_nodes,
            edge_probability=request.edge_probability,
            seed=request.seed
        )

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get(
                "error", "Network creation failed"))

        return MCPResponse(success=True, data=result)

    except ImportError:
        # Fallback to legacy implementation
        logger.warning(
            "New network tools not available, using legacy implementation")
        return await _legacy_create_network(request)
    except Exception as e:
        logger.error(f"Error creating network: {e}")
        return MCPResponse(success=False, error=str(e))


@app.post("/tools/apply_layout", response_model=MCPResponse)
async def apply_layout_tool(request: LayoutRequest):
    """Apply layout algorithm (MCP tool style)."""
    try:
        from tools.layout_algorithms import apply_layout_algorithm

        result = apply_layout_algorithm(
            graphml_content=request.graphml_content,
            layout_type=request.layout_type,
            **request.layout_params
        )

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get(
                "error", "Layout application failed"))

        return MCPResponse(success=True, data=result)

    except ImportError:
        logger.warning(
            "New layout tools not available, using legacy implementation")
        return await _legacy_apply_layout(request)
    except Exception as e:
        logger.error(f"Error applying layout: {e}")
        return MCPResponse(success=False, error=str(e))


@app.post("/tools/calculate_centrality", response_model=MCPResponse)
async def calculate_centrality_tool(request: CentralityRequest):
    """Calculate centrality metrics (MCP tool style)."""
    try:
        from tools.centrality_metrics import calculate_centrality_metric

        result = calculate_centrality_metric(
            graphml_content=request.graphml_content,
            centrality_type=request.centrality_type,
            **request.centrality_params
        )

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get(
                "error", "Centrality calculation failed"))

        return MCPResponse(success=True, data=result)

    except ImportError:
        logger.warning(
            "New centrality tools not available, using legacy implementation")
        return await _legacy_calculate_centrality(request)
    except Exception as e:
        logger.error(f"Error calculating centrality: {e}")
        return MCPResponse(success=False, error=str(e))


@app.post("/tools/create_visualization", response_model=MCPResponse)
async def create_visualization_tool(request: VisualizationRequest):
    """Create visualization data (MCP tool style)."""
    try:
        from tools.visualization import create_visualization_data

        result = create_visualization_data(
            graphml_content=request.graphml_content,
            metric_values=request.metric_values,
            color_scheme=request.color_scheme,
            size_range=request.size_range
        )

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get(
                "error", "Visualization creation failed"))

        return MCPResponse(success=True, data=result)

    except ImportError:
        logger.warning("New visualization tools not available")
        return MCPResponse(success=False, error="Visualization tools not available")
    except Exception as e:
        logger.error(f"Error creating visualization: {e}")
        return MCPResponse(success=False, error=str(e))

# --- Legacy Tool Implementations (Fallback) ---


async def _legacy_create_network(request: NetworkCreationRequest) -> MCPResponse:
    """Legacy network creation implementation."""
    try:
        import networkx as nx
        import random
        import io

        if request.seed is not None:
            random.seed(request.seed)

        # Create random graph
        G = nx.gnp_random_graph(
            request.num_nodes, request.edge_probability, seed=request.seed)

        # Ensure connectivity
        if not nx.is_connected(G) and request.num_nodes > 1:
            components = list(nx.connected_components(G))
            largest_component = max(components, key=len)
            for component in components:
                if component != largest_component:
                    node_from = random.choice(list(component))
                    node_to = random.choice(list(largest_component))
                    G.add_edge(node_from, node_to)

        # Add labels
        for node in G.nodes():
            G.nodes[node]['label'] = f"Node {node}"

        # Convert to GraphML
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        graphml_content = output.read().decode("utf-8")

        return MCPResponse(
            success=True,
            data={
                "graphml_content": graphml_content,
                "graph_info": {
                    "nodes": G.number_of_nodes(),
                    "edges": G.number_of_edges(),
                    "is_connected": nx.is_connected(G)
                }
            }
        )

    except Exception as e:
        return MCPResponse(success=False, error=str(e))


async def _legacy_apply_layout(request: LayoutRequest) -> MCPResponse:
    """Legacy layout application implementation."""
    try:
        import networkx as nx
        import io

        # Parse GraphML
        content_io = io.BytesIO(request.graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)

        # Apply layout
        if request.layout_type == "spring":
            pos = nx.spring_layout(G, **request.layout_params)
        elif request.layout_type == "circular":
            pos = nx.circular_layout(G, **request.layout_params)
        else:
            pos = nx.spring_layout(G)  # Default fallback

        # Convert positions
        positions = {
            str(node): {"x": float(coord[0]), "y": float(coord[1])}
            for node, coord in pos.items()
        }

        # Add positions to graph
        for node, coord in pos.items():
            G.nodes[node]['x'] = float(coord[0])
            G.nodes[node]['y'] = float(coord[1])

        # Convert back to GraphML
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        updated_graphml = output.read().decode("utf-8")

        return MCPResponse(
            success=True,
            data={
                "layout_type": request.layout_type,
                "positions": positions,
                "graphml_content": updated_graphml
            }
        )

    except Exception as e:
        return MCPResponse(success=False, error=str(e))


async def _legacy_calculate_centrality(request: CentralityRequest) -> MCPResponse:
    """Legacy centrality calculation implementation."""
    try:
        import networkx as nx
        import io

        # Parse GraphML
        content_io = io.BytesIO(request.graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)

        # Calculate centrality
        if request.centrality_type == "degree":
            centrality = nx.degree_centrality(G)
        elif request.centrality_type == "betweenness":
            centrality = nx.betweenness_centrality(
                G, **request.centrality_params)
        elif request.centrality_type == "closeness":
            centrality = nx.closeness_centrality(
                G, **request.centrality_params)
        elif request.centrality_type == "eigenvector":
            centrality = nx.eigenvector_centrality(
                G, **request.centrality_params)
        else:
            centrality = nx.degree_centrality(G)  # Default fallback

        # Convert to string keys
        centrality_values = {str(k): float(v) for k, v in centrality.items()}

        return MCPResponse(
            success=True,
            data={
                "centrality_type": request.centrality_type,
                "values": centrality_values,
                "statistics": {
                    "min": min(centrality_values.values()),
                    "max": max(centrality_values.values()),
                    "mean": sum(centrality_values.values()) / len(centrality_values)
                }
            }
        )

    except Exception as e:
        return MCPResponse(success=False, error=str(e))

# --- Cache Management Endpoints ---


@app.delete("/cache/clear", response_model=MCPResponse)
async def clear_cache():
    """Clear all caches."""
    try:
        server_context.clear_caches()
        return MCPResponse(success=True, data={"message": "All caches cleared"})
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return MCPResponse(success=False, error=str(e))

# --- Error Handlers (MCP-style) ---


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions in MCP format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=MCPResponse(
            success=False,
            error=exc.detail,
            timestamp=datetime.now().isoformat()
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions in MCP format."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=MCPResponse(
            success=False,
            error="Internal server error",
            timestamp=datetime.now().isoformat()
        ).dict()
    )

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting NetworkX MCP Server (FastAPI)...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
