"""
Test configuration and fixtures for API testing.
"""

import os
import pytest
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from main import app
from database import Base, get_db
import models
import auth

# Test database configuration
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
engine = create_engine(
    TEST_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

# Create test session
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    """Create database engine for tests."""
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(db_engine):
    """Create a fresh database session for each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    """Create FastAPI test client with test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock the NetworkX MCP URL to avoid external calls during tests
    with patch.dict(os.environ, {'NETWORKX_MCP_URL': 'http://test-networkx-mcp:8001'}):
        with TestClient(app) as test_client:
            yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture
def test_user_data():
    """Test user data for creating users."""
    return {
        "username": "testuser",
        "password": "testpassword123"
    }

@pytest.fixture
def test_user(db_session, test_user_data):
    """Create a test user in the database."""
    hashed_password = auth.get_password_hash(test_user_data["password"])
    db_user = models.User(
        username=test_user_data["username"],
        hashed_password=hashed_password
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)
    return db_user

@pytest.fixture
def auth_headers(client, test_user_data):
    """Get authentication headers for API requests."""
    response = client.post(
        "/auth/token",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_graphml():
    """Sample GraphML content for testing network operations."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
         http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="1">
      <data key="name">Node 1</data>
    </node>
    <node id="2">
      <data key="name">Node 2</data>
    </node>
    <node id="3">
      <data key="name">Node 3</data>
    </node>
    <edge id="e1" source="1" target="2"/>
    <edge id="e2" source="2" target="3"/>
    <edge id="e3" source="3" target="1"/>
  </graph>
</graphml>"""

@pytest.fixture
def test_conversation(db_session, test_user):
    """Create a test conversation."""
    conversation = models.Conversation(
        title="Test Conversation",
        user_id=test_user.id
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation

@pytest.fixture
def test_network(db_session, test_conversation, sample_graphml):
    """Create a test network associated with a conversation."""
    network = models.Network(
        name="Test Network",
        conversation_id=test_conversation.id,
        graphml_content=sample_graphml
    )
    db_session.add(network)
    db_session.commit()
    db_session.refresh(network)
    return network

@pytest.fixture
def mock_networkx_mcp():
    """Mock NetworkX MCP server responses."""
    from unittest.mock import AsyncMock
    
    class MockResponse:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json_data = json_data or {}
        
        def json(self):
            return self._json_data
        
        @property
        def text(self):
            return str(self._json_data)
    
    mock_client = AsyncMock()
    
    # Mock successful GraphML conversion
    mock_client.post.return_value = MockResponse(200, {
        "success": True,
        "graphml_content": "<?xml version='1.0' encoding='UTF-8'?>..."
    })
    
    return mock_client

@pytest.fixture
def temp_file():
    """Create a temporary file for testing file uploads."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.graphml', delete=False) as f:
        f.write("""<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="undirected">
    <node id="1"/>
    <node id="2"/>
    <edge source="1" target="2"/>
  </graph>
</graphml>""")
        temp_file_path = f.name
    
    yield temp_file_path
    
    # Cleanup
    try:
        os.unlink(temp_file_path)
    except FileNotFoundError:
        pass