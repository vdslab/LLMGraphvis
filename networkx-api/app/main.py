from fastapi import FastAPI

from app.api.v1.endpoints import analysis, layout, networks, subgraphs, visualization
from app.core.logging import get_logger
from app.mcp_server import mcp
from app.middleware.logging import LoggingMiddleware

logger = get_logger(__name__)

# Database schema is managed exclusively by Alembic in the backend service
# (see backend/alembic/); this service only consumes the shared tables.

app = FastAPI(
    title="NetworkX API",
    description="API for NetworkX graph operations",
    version="1.0.0",
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

app.mount("/mcp", mcp.sse_app())


@app.get("/health")
def health_check():
    return {"status": "ok"}


# analysis must be registered before networks: its literal route
# /{network_id}/nodes/top would otherwise be captured by the
# /{network_id}/nodes/{node_id} wildcard in networks.
app.include_router(
    analysis.router, prefix="/api/v1/networks", tags=["analysis"]
)  # Analysis is typically under a network
app.include_router(networks.router, prefix="/api/v1/networks", tags=["networks"])
app.include_router(layout.router, prefix="/api/v1/networks", tags=["layout"])
app.include_router(
    visualization.router, prefix="/api/v1/networks", tags=["visualization"]
)
app.include_router(subgraphs.router, prefix="/api/v1/networks", tags=["subgraphs"])
