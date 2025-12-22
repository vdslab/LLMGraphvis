import pytest_asyncio
from app.main import app
from httpx import ASGITransport, AsyncClient

# By default, pytest-asyncio treats "async" fixtures as function-scoped.
# If you need broader scope, you must configure it.


@pytest_asyncio.fixture
async def async_client():
    """
    Fixture for creating an async client to test FastAPI endpoints.
    """
    # Use ASGITransport for direct app testing without a running server
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
