from fastapi import FastAPI
from app.api.v1.endpoints import tools
from app.core.database import engine, Base

# Create database tables
# Note: In a real microservices setup with shared DB, we need to be careful about who creates tables.
# Here, NetworkXAPI owns the Network/Node/Edge tables.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="GraphVisAgent NetworkXAPI")

app.include_router(tools.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
