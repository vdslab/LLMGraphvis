import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import auth, chat, networks
from app.core.logging import get_logger
from app.middleware.logging import LoggingMiddleware

logger = get_logger(__name__)

# Database schema is managed exclusively by Alembic (see backend/alembic/),
# which runs via `alembic upgrade head` before this app starts (see
# docker-compose.yml / backend/Dockerfile). Do not create tables here.
# Base.metadata.create_all(bind=engine)

# Create FastAPI app with Swagger UI configuration
app = FastAPI(
    title="GraphVisAgent Backend",
    description="API with authentication support for both browser clients (cookies) and API clients (Bearer tokens).",
    version="1.0.0",
    swagger_ui_parameters={
        "persistAuthorization": True,  # Remember authorization between refreshes
        "tryItOutEnabled": True,  # Enable testing endpoints directly from Swagger
        "docExpansion": "none",  # Collapse all endpoints by default
        "defaultModelsExpandDepth": 1,  # Limit models display depth
    },
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}"
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    {"path": "/health", "method": "GET"},
    {"path": "/auth/register", "method": "POST"},
    {"path": "/auth/token", "method": "POST"},
    {"path": "/openapi.json", "method": "GET"},
    {"path": "/docs", "method": "GET"},
    {"path": "/redoc", "method": "GET"},
]


# Custom OpenAPI schema to include security scheme and exclude public endpoints
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add OAuth2 password flow security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {"password": {"tokenUrl": "/auth/token", "scopes": {}}},
        }
    }

    # Configure security for all paths
    if "paths" in openapi_schema:
        for path, path_item in openapi_schema["paths"].items():
            for method, operation in path_item.items():
                # Skip security for public endpoints
                is_public = False
                for endpoint in PUBLIC_ENDPOINTS:
                    if (
                        path == endpoint["path"]
                        and method.upper() == endpoint["method"]
                    ):
                        is_public = True
                        break

                # Add security requirement for protected endpoints only
                if not is_public:
                    operation["security"] = [{"OAuth2PasswordBearer": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# CORS configuration — comma-separated list, e.g. CORS_ORIGINS=http://localhost,http://localhost:5173
origins = [
    o.strip()
    for o in (os.getenv("CORS_ORIGINS") or "http://localhost,http://localhost:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(networks.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to GraphVisAgent API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
