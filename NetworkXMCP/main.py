"""
NetworkX MCP Server (Clean Implementation)
==========================================

Proper FastAPI MCP server implementation following MCP specification
with clean tool definitions for network analysis and visualization.
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import networkx as nx
import json
import io
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("networkx_mcp")

# Create FastAPI app
app = FastAPI(
    title="NetworkX MCP Server",
    description="Network analysis and visualization server using NetworkX",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models


class GraphMLInput(BaseModel):
    graphml_content: str = Field(..., description="GraphML content")


class LayoutRequest(GraphMLInput):
    layout_type: str = Field("spring", description="Layout algorithm")
    layout_params: Dict[str, Any] = Field(default_factory=dict)


class CentralityRequest(GraphMLInput):
    centrality_type: str = Field("degree", description="Centrality type")
    centrality_params: Dict[str, Any] = Field(default_factory=dict)

# Helper functions


def parse_graphml_string(graphml_content: str) -> nx.Graph:
    """Parse GraphML string into NetworkX graph"""
    try:
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)
        logger.info(
            f"Parsed GraphML with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G
    except Exception as e:
        logger.error(f"Error parsing GraphML: {e}")
        raise ValueError(f"Invalid GraphML content: {e}")


def graph_to_graphml(G: nx.Graph) -> str:
    """Convert NetworkX graph to GraphML string"""
    try:
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        return output.read().decode("utf-8")
    except Exception as e:
        logger.error(f"Error converting to GraphML: {e}")
        raise ValueError(f"Failed to convert graph to GraphML: {e}")


def apply_layout_algorithm(G: nx.Graph, layout_type: str, **kwargs) -> Dict[str, Dict[str, float]]:
    """Apply layout algorithm and return node positions"""
    layout_functions = {
        "spring": nx.spring_layout,
        "circular": nx.circular_layout,
        "random": nx.random_layout,
        "spectral": nx.spectral_layout,
        "shell": nx.shell_layout,
        "kamada_kawai": nx.kamada_kawai_layout,
        "fruchterman_reingold": nx.fruchterman_reingold_layout,
    }

    # Handle special layouts
    if layout_type == "planar":
        if nx.is_planar(G):
            positions = nx.planar_layout(G, **kwargs)
        else:
            logger.warning(
                "Graph is not planar, falling back to spring layout")
            positions = nx.spring_layout(G, **kwargs)
    else:
        layout_func = layout_functions.get(layout_type, nx.spring_layout)
        positions = layout_func(G, **kwargs)

    # Convert to JSON-serializable format
    return {str(k): {"x": float(v[0]), "y": float(v[1])} for k, v in positions.items()}


def calculate_centrality_metrics(G: nx.Graph, centrality_type: str, **kwargs) -> Dict[str, float]:
    """Calculate centrality metrics for the graph"""
    centrality_functions = {
        "degree": nx.degree_centrality,
        "betweenness": nx.betweenness_centrality,
        "closeness": nx.closeness_centrality,
        "eigenvector": nx.eigenvector_centrality,
        "pagerank": nx.pagerank,
    }

    centrality_func = centrality_functions.get(centrality_type)
    if not centrality_func:
        raise ValueError(f"Unknown centrality type: {centrality_type}")

    try:
        centrality = centrality_func(G, **kwargs)
        return {str(k): float(v) for k, v in centrality.items()}
    except Exception as e:
        logger.error(f"Error calculating {centrality_type} centrality: {e}")
        raise ValueError(
            f"Failed to calculate {centrality_type} centrality: {e}")

# Health check


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# MCP Tools


@app.post("/tools/get_sample_network")
async def get_sample_network():
    """Generate a sample network and return it as GraphML."""
    try:
        # Create random graph
        num_nodes = 20
        edge_probability = 0.2
        G = nx.gnp_random_graph(num_nodes, edge_probability, seed=42)

        # Ensure connectivity
        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            largest_component = max(components, key=len)
            for component in components:
                if component != largest_component:
                    node_from = list(component)[0]
                    node_to = list(largest_component)[0]
                    G.add_edge(node_from, node_to)

        # Apply spring layout and add node attributes
        positions = nx.spring_layout(G, k=1.0, iterations=50, seed=42)

        for node in G.nodes():
            pos = positions.get(node, (0, 0))
            G.nodes[node]['x'] = str(float(pos[0]))
            G.nodes[node]['y'] = str(float(pos[1]))
            G.nodes[node]['name'] = f"Node {node}"
            G.nodes[node]['size'] = "5.0"
            G.nodes[node]['color'] = "#1d4ed8"

        # Add edge attributes
        for u, v in G.edges():
            G.edges[u, v]['width'] = "1.0"
            G.edges[u, v]['color'] = "#94a3b8"

        graphml_content = graph_to_graphml(G)
        logger.info(
            f"Generated sample network with {G.number_of_nodes()} nodes")

        return {
            "result": {
                "success": True,
                "graphml_content": graphml_content
            }
        }

    except Exception as e:
        logger.error(f"Error generating sample network: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/change_layout")
async def change_layout(request: LayoutRequest):
    """Apply a layout algorithm to the network."""
    try:
        G = parse_graphml_string(request.graphml_content)
        positions = apply_layout_algorithm(
            G, request.layout_type, **request.layout_params)

        logger.info(
            f"Applied {request.layout_type} layout to graph with {G.number_of_nodes()} nodes")

        return {
            "result": {
                "success": True,
                "layout_type": request.layout_type,
                "positions": positions
            }
        }

    except Exception as e:
        logger.error(f"Error applying layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/calculate_centrality")
async def calculate_centrality(request: CentralityRequest):
    """Calculate centrality metrics for network nodes."""
    try:
        G = parse_graphml_string(request.graphml_content)
        centrality_values = calculate_centrality_metrics(
            G, request.centrality_type, **request.centrality_params)

        logger.info(
            f"Calculated {request.centrality_type} centrality for {G.number_of_nodes()} nodes")

        return {
            "result": {
                "success": True,
                "centrality_type": request.centrality_type,
                "centrality_values": centrality_values
            }
        }

    except Exception as e:
        logger.error(f"Error calculating centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/convert_to_standard_graphml")
async def convert_to_standard_graphml(request: GraphMLInput):
    """Convert GraphML to standard format with proper node and edge attributes."""
    try:
        G = parse_graphml_string(request.graphml_content)

        # Ensure all nodes have required attributes
        for node in G.nodes():
            if 'name' not in G.nodes[node]:
                G.nodes[node]['name'] = f"Node {node}"
            if 'x' not in G.nodes[node]:
                G.nodes[node]['x'] = "0.0"
            if 'y' not in G.nodes[node]:
                G.nodes[node]['y'] = "0.0"
            if 'size' not in G.nodes[node]:
                G.nodes[node]['size'] = "5.0"
            if 'color' not in G.nodes[node]:
                G.nodes[node]['color'] = "#1d4ed8"

        # Ensure all edges have required attributes
        for u, v in G.edges():
            if 'width' not in G.edges[u, v]:
                G.edges[u, v]['width'] = "1.0"
            if 'color' not in G.edges[u, v]:
                G.edges[u, v]['color'] = "#94a3b8"

        standardized_graphml = graph_to_graphml(G)
        logger.info(f"Standardized GraphML with {G.number_of_nodes()} nodes")

        return {
            "success": True,
            "graphml_content": standardized_graphml
        }

    except Exception as e:
        logger.error(f"Error standardizing GraphML: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/analyze_network_properties")
async def analyze_network_properties(request: GraphMLInput):
    """Analyze comprehensive network properties."""
    try:
        G = parse_graphml_string(request.graphml_content)

        # Basic properties
        basic_props = {
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges(),
            "is_connected": nx.is_connected(G),
            "is_directed": G.is_directed(),
            "density": nx.density(G)
        }

        # Connectivity
        connectivity = {
            "num_components": nx.number_connected_components(G),
            "average_clustering": nx.average_clustering(G),
            "transitivity": nx.transitivity(G)
        }

        # Path metrics (only for connected graphs)
        path_metrics = {}
        if nx.is_connected(G):
            path_metrics = {
                "diameter": nx.diameter(G),
                "average_shortest_path": nx.average_shortest_path_length(G),
                "radius": nx.radius(G)
            }

        # Degree statistics
        degrees = [d for n, d in G.degree()]
        degree_stats = {
            "degree_sequence": degrees,
            "average_degree": sum(degrees) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0,
            "degree_assortativity": nx.degree_assortativity_coefficient(G)
        }

        results = {
            "basic_properties": basic_props,
            "connectivity": connectivity,
            "path_metrics": path_metrics,
            "degree_statistics": degree_stats
        }

        return {
            "result": {
                "success": True,
                "analysis": results
            }
        }

    except Exception as e:
        logger.error(f"Error analyzing network: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting NetworkX MCP Server...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
