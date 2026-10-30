from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from app.api.v1.endpoints import analysis, layout, networks, subgraphs, visualization
from app.core.logging import get_logger
from app.mcp_server import mcp
from app.middleware.logging import LoggingMiddleware

logger = get_logger(__name__)

# Database schema is managed exclusively by Alembic in the backend service
# (see backend/alembic/); this service only consumes the shared tables.


def create_app():
    """Build a host with its own MCP session-manager lifecycle."""
    transport = mcp.streamable_http_app(
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            allowed_hosts=[
                "networkx-api:*",
                "evaluation-networkx:*",
                "localhost:*",
                "127.0.0.1:*",
                "testserver",
            ],
        ),
    )
    manager = mcp.session_manager

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    app = FastAPI(
        title="NetworkX API",
        description="API for NetworkX graph operations",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(LoggingMiddleware)
    app.mount("/mcp", transport)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    # Literal /nodes/top must precede the /nodes/{node_id} wildcard.
    app.include_router(analysis.router, prefix="/api/v1/networks", tags=["analysis"])
    app.include_router(networks.router, prefix="/api/v1/networks", tags=["networks"])
    app.include_router(layout.router, prefix="/api/v1/networks", tags=["layout"])
    app.include_router(
        visualization.router, prefix="/api/v1/networks", tags=["visualization"]
    )
    app.include_router(subgraphs.router, prefix="/api/v1/networks", tags=["subgraphs"])
    return app


app = create_app()
