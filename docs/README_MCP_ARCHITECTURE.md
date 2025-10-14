# NetworkXMCP MCP Server Architecture

This document outlines the architecture and best practices for the NetworkXMCP server, following the Model Context Protocol (MCP) specification for reliable, modular, and secure AI agent integration.

## File Structure

```
NetworkXMCP/
├── server.py                  # Pure MCP server entrypoint (recommended)
├── main.py                    # FastAPI HTTP server (compatibility layer)
├── core/                      # Core utilities and context management
│   ├── __init__.py
│   ├── context.py             # Server context, caching, lifespan
│   └── graph_utils.py         # Graph processing utilities
├── tools/                     # MCP tools (by function)
│   ├── __init__.py
│   ├── network_operations.py  # Network creation tools
│   ├── layout_algorithms.py   # Layout computation tools
│   ├── centrality_metrics.py  # Centrality calculation tools
│   ├── graph_io.py            # Import/export, format conversion
│   └── visualization.py       # Visualization tools
├── resources/                 # MCP resources (read-only data)
│   ├── __init__.py
│   ├── graph_resources.py     # Cached graph access
│   └── cache_resources.py     # Cache statistics
└── ... (tests, Dockerfile, etc.)
```

## MCP Best Practices

### Logging

- All logs **MUST** go to `stderr` (never `stdout`)
- Use structured logging with log levels
- Rate limit log messages
- Include relevant context in log data
- Use consistent logger names
- Remove or mask sensitive information

### Security

- Validate all resource URIs
- Implement access controls for sensitive resources
- Properly encode binary data
- Check resource permissions before operations

### Error Handling

- Use consistent error response format
- Propagate exceptions with context
- Graceful fallback if dependencies are missing

### Modularity

- Tools organized by function (network, layout, centrality, I/O, visualization)
- Resources separated from tools
- Core utilities separated from business logic

### Type Safety

- Use Pydantic models for requests/responses
- Type hints throughout codebase

## Usage

**Pure MCP server (recommended):**

```python
from server import mcp
if __name__ == "__main__":
    mcp.run()
```

**FastAPI HTTP server (compatibility):**

```python
import uvicorn
from main import app
uvicorn.run(app, host="0.0.0.0", port=8001)
```

## Example MCP Tools

```python
@mcp.tool()
def create_random_graph(num_nodes: int = 20, edge_probability: float = 0.2, seed: Optional[int] = None) -> dict:
    """Create a random graph using Erdős–Rényi model."""

@mcp.tool()
def apply_spring_layout(graphml_content: str, k: float = None, iterations: int = 50) -> dict:
    """Apply spring layout algorithm."""

@mcp.tool()
def calculate_degree_centrality(graphml_content: str) -> dict:
    """Calculate degree centrality for all nodes."""
```

## Example MCP Resources

```python
@mcp.resource("graph://cached/{graph_id}")
def get_cached_graph(graph_id: str) -> str:
    """Access cached graph by ID."""

@mcp.resource("cache://stats")
def get_cache_statistics() -> str:
    """Get cache usage statistics."""
```

## FastAPI Compatibility

The FastAPI-MCP hybrid maintains backward compatibility. Example endpoints:

- `GET /` — Server info
- `GET /health` — Health check
- `GET /resources/graphs` — List cached graphs
- `POST /tools/create_network` — Create network
- `POST /tools/apply_layout` — Apply layout
- `POST /tools/calculate_centrality` — Calculate centrality

All endpoints use a standardized response format:

```json
{
    "success": true,
    "data": { ... },
    "error": null,
    "timestamp": "2025-10-10T23:24:00.000Z"
}
```

## Summary of Best Practices

- **Separation of concerns:** Core, tools, and resources are modular
- **Consistent error handling:** Standardized error format, exception logging
- **Type safety:** Pydantic models, type hints, validation
- **Caching:** Server-wide context, efficient storage, cache stats
- **Logging:** stderr-only, structured, rate-limited, sensitive info masked

## Development & Testing

- **Validate structure:**
  ```bash
  python validate_structure.py
  ```
- **Run MCP server:**
  ```bash
  python server.py
  ```
- **Run FastAPI server:**
  ```bash
  python main.py
  ```
- **Docker:**
  ```yaml
  services:
    networkx-mcp:
      build: ./NetworkXMCP
      ports:
        - "8001:8001"
  ```

## Migration Guide

- **Existing users:** FastAPI endpoints remain functional; MCP tools add new features
- **New deployments:** Use `server.py` for pure MCP, `main.py` for FastAPI compatibility

## Dependencies

**Required:**

- `networkx` — Graph analysis
- `pydantic` — Data validation
- `fastapi` — Web framework (if using FastAPI)

**Optional:**

- `mcp` — Pure MCP server
- `fastapi-mcp` — FastAPI-MCP integration
- `uvicorn` — ASGI server

## Conclusion

This architecture ensures:

- MCP best practices compliance
- Backward compatibility with FastAPI
- Modular, extensible design
- Type safety and validation
- Robust error handling
- Secure, efficient context and resource management

Follow this structure to maintain a reliable, maintainable, and standards-compliant MCP server implementation.
