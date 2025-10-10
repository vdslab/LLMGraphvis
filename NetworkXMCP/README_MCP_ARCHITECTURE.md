# NetworkX MCP Server - Best Practices Architecture

This document describes the redesigned NetworkX MCP server that follows Model Context Protocol best practices while maintaining FastAPI compatibility.

## Architecture Overview

The new architecture separates concerns properly and follows MCP design patterns:

```
NetworkXMCP/
├── server.py                    # Pure MCP server (recommended)
├── main_fastapi_mcp.py         # FastAPI-MCP hybrid (current)
├── main.py                     # Legacy FastAPI server
├── core/                       # Core utilities and context
│   ├── __init__.py
│   ├── context.py             # Server context and caching
│   └── graph_utils.py         # Graph processing utilities
├── tools/                      # MCP tools (organized by function)
│   ├── __init__.py
│   ├── network_operations.py  # Network creation tools
│   ├── layout_algorithms.py   # Layout computation tools
│   ├── centrality_metrics.py  # Centrality calculation tools
│   ├── graph_io.py            # Import/export tools
│   ├── visualization.py       # Visualization tools
│   └── centrality_persistence.py # Legacy centrality tools
└── resources/                  # MCP resources (read-only data)
    ├── __init__.py
    ├── graph_resources.py      # Cached graph access
    └── cache_resources.py      # Cache statistics
```

## Key Improvements

### 1. **Proper MCP Logging**

- Uses `stderr` for all logging (MCP requirement)
- Structured logging with proper levels
- No `print()` or `stdout` usage that corrupts JSON-RPC

### 2. **Modular Tool Organization**

- **Network Operations**: Random graphs, small-world, scale-free
- **Layout Algorithms**: Spring, circular, hierarchical layouts
- **Centrality Metrics**: Degree, betweenness, closeness, eigenvector, PageRank
- **Graph I/O**: Import, export, format conversion, statistics
- **Visualization**: Color schemes, node sizing, legends

### 3. **MCP Resources**

- `graph://cached/{graph_id}` - Access cached graphs
- `graph://list` - List all cached graphs
- `cache://stats` - Cache statistics
- `cache://centrality` - Centrality calculations

### 4. **Proper Context Management**

- Server-wide context with lifespan management
- Shared caching across tools
- Type-safe context access

### 5. **Error Handling**

- Consistent error response format
- Proper exception propagation
- Graceful fallbacks when dependencies missing

## Usage Patterns

### Pure MCP Server (Recommended)

```python
# Use server.py for pure MCP implementation
from server import mcp

if __name__ == "__main__":
    mcp.run()
```

### FastAPI-MCP Hybrid (Current)

```python
# Use main_fastapi_mcp.py for FastAPI + MCP
import uvicorn
from main_fastapi_mcp import app

uvicorn.run(app, host="0.0.0.0", port=8001)
```

## MCP Tools

### Network Creation Tools

```python
@mcp.tool()
def create_random_graph(num_nodes: int = 20, edge_probability: float = 0.2, seed: Optional[int] = None) -> Dict[str, Any]:
    """Create a random graph using Erdős–Rényi model."""
```

### Layout Tools

```python
@mcp.tool()
def apply_spring_layout(graphml_content: str, k: Optional[float] = None, iterations: int = 50) -> Dict[str, Any]:
    """Apply spring layout algorithm."""
```

### Centrality Tools

```python
@mcp.tool()
def calculate_degree_centrality(graphml_content: str) -> Dict[str, Any]:
    """Calculate degree centrality for all nodes."""
```

## MCP Resources

### Graph Resources

```python
@mcp.resource("graph://cached/{graph_id}")
def get_cached_graph(graph_id: str) -> str:
    """Access cached graph by ID."""
```

### Cache Resources

```python
@mcp.resource("cache://stats")
def get_cache_statistics() -> str:
    """Get cache usage statistics."""
```

## FastAPI Compatibility

The FastAPI-MCP hybrid maintains backward compatibility:

### Endpoints

- `GET /` - Server information
- `GET /health` - Health check
- `GET /resources/graphs` - List cached graphs
- `POST /tools/create_network` - Create network
- `POST /tools/apply_layout` - Apply layout
- `POST /tools/calculate_centrality` - Calculate centrality

### Request/Response Format

All endpoints use the standardized `MCPResponse` format:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2025-10-10T23:24:00.000Z"
}
```

## Best Practices Implemented

### 1. **Separation of Concerns**

- Core utilities separated from business logic
- Tools organized by functionality
- Resources separated from tools

### 2. **Proper Error Handling**

- Consistent error response format
- Proper exception logging
- Graceful degradation

### 3. **Type Safety**

- Pydantic models for all requests/responses
- Type hints throughout codebase
- Structured data validation

### 4. **Caching Strategy**

- Server-wide context management
- Efficient data storage
- Cache statistics and monitoring

### 5. **Logging Best Practices**

- stderr-only logging (MCP requirement)
- Structured log messages
- Appropriate log levels

## Development and Testing

### Structure Validation

```bash
python validate_structure.py
```

### Running the Server

```bash
# Pure MCP server
python server.py

# FastAPI-MCP hybrid
python main_fastapi_mcp.py

# Legacy FastAPI
python main.py
```

### Docker Integration

The new architecture is fully compatible with the existing Docker setup:

```yaml
# docker-compose.yml remains unchanged
services:
  networkx-mcp:
    build: ./NetworkXMCP
    ports:
      - "8001:8001"
```

## Migration Guide

### For Existing Users

1. Current FastAPI endpoints remain functional
2. New MCP tools provide enhanced functionality
3. Gradual migration path available

### For New Deployments

1. Use `server.py` for pure MCP implementation
2. Use `main_fastapi_mcp.py` for FastAPI compatibility
3. Follow MCP client integration patterns

## Dependencies

### Required

- `networkx` - Graph analysis
- `pydantic` - Data validation
- `fastapi` - Web framework (if using FastAPI mode)

### Optional

- `mcp` - Pure MCP server functionality
- `fastapi-mcp` - FastAPI-MCP integration
- `uvicorn` - ASGI server

## Conclusion

This redesigned architecture provides:

- ✅ MCP best practices compliance
- ✅ Backward compatibility with FastAPI
- ✅ Proper separation of concerns
- ✅ Type safety and validation
- ✅ Comprehensive error handling
- ✅ Efficient caching and context management

The modular design makes it easy to extend functionality while maintaining clean interfaces and proper MCP protocol compliance.
