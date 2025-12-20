from fastapi import FastAPI

from app.core.database import Base, engine
from app.core.logging import get_logger
from app.middleware.logging import LoggingMiddleware

logger = get_logger(__name__)

# Create database tables
# Note: In a real microservices setup with shared DB, we need to be careful about who creates tables.
# Here, NetworkXAPI owns the Network/Node/Edge tables.
logger.info("Starting table creation...")
try:
    logger.info(f"Registered tables: {list(Base.metadata.tables.keys())}")
    Base.metadata.create_all(bind=engine)
    logger.info("Table creation completed.")
except Exception as e:
    logger.error(f"Table creation FAILED: {e}")

app = FastAPI(
    title="NetworkX API",
    description="API for NetworkX graph operations",
    version="1.0.0",
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

from app.mcp_server import mcp

app.mount("/mcp", mcp.sse_app())


@app.get("/health")
def health_check():
    return {"status": "ok"}


from app.api.v1.endpoints import analysis, layout, networks, subgraphs, visualization

app.include_router(networks.router, prefix="/api/v1/networks", tags=["networks"])
app.include_router(
    analysis.router, prefix="/api/v1/networks", tags=["analysis"]
)  # Analysis is typically under a network
app.include_router(layout.router, prefix="/api/v1/networks", tags=["layout"])
app.include_router(
    visualization.router, prefix="/api/v1/networks", tags=["visualization"]
)
app.include_router(subgraphs.router, prefix="/api/v1/networks", tags=["subgraphs"])
