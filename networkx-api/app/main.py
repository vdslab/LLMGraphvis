from fastapi import FastAPI
from app.api.v1.endpoints import tools
from app.core.database import engine, Base

# Create database tables
# Note: In a real microservices setup with shared DB, we need to be careful about who creates tables.
# Here, NetworkXAPI owns the Network/Node/Edge tables.
print("DEBUG: Starting table creation...", flush=True)
try:
    print(f"DEBUG: Registered tables: {list(Base.metadata.tables.keys())}", flush=True)
    Base.metadata.create_all(bind=engine)
    print("DEBUG: Table creation completed.", flush=True)
except Exception as e:
    print(f"DEBUG: Table creation FAILED: {e}", flush=True)

app = FastAPI(title="GraphVisAgent NetworkXAPI")

app.include_router(tools.router)

from app.mcp_server import mcp
app.mount("/sse", mcp.sse_app(mount_path="/sse"))

@app.get("/health")
def health_check():
    return {"status": "ok"}
