"""
Database configuration for the FastAPI application.

This file sets up the SQLAlchemy engine, session factory, and a dependency
for creating database sessions.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database URL from environment variable or use default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/graphvis")
logger.info(f"DATABASE_URL set to: {DATABASE_URL}")

# Create SQLAlchemy engine with specific connection parameters
engine_args = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

engine = create_engine(DATABASE_URL, **engine_args)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Function to get database session
def get_db():
    """
    Provides a database session for dependency injection.

    Yields:
        A new database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
