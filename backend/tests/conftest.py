
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from common.models import Base
from app.core.database import get_db
from app.main import app
from httpx import AsyncClient, ASGITransport

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def setup_db_schema():
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
async def async_client(db):
    """
    Async client for testing async endpoints.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass  # Session lifecycle managed by db fixture

    app.dependency_overrides[get_db] = override_get_db
    
    # Create transport for the app
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def db(setup_db_schema):
    """
    Creates a fresh database session for a test.
    Rolls back transaction after test to ensure isolation.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
