from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, chat
from database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="GraphVisAgent Backend")

# CORS configuration
origins = [
    "http://localhost:5173",  # Frontend
    "http://localhost:3000",
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

@app.get("/health")
def health_check():
    return {"status": "ok"}
