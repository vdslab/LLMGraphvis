# FastAPI Testing Guide

This guide provides comprehensive information about running and maintaining the test suite for the LLMGraphvis project, which includes both API and NetworkXMCP services.

## Overview

The test suite is built using FastAPI's testing framework based on the [official FastAPI testing tutorial](https://fastapi.tiangolo.com/tutorial/testing/). It includes:

- **Unit tests** for individual components
- **Integration tests** for service communication
- **API endpoint tests** with authentication
- **Network analysis tests** for graph operations
- **Coverage reporting** for code quality metrics

## Test Structure

```
├── API/
│   ├── conftest.py           # Test fixtures and configuration
│   ├── test_auth.py          # Authentication tests
│   ├── test_network.py       # Network operations tests
│   ├── test_chat.py          # Chat functionality tests
│   ├── test_main.py          # Main application tests
│   └── test_integration.py   # API-NetworkXMCP integration tests
├── NetworkXMCP/
│   ├── conftest.py           # NetworkXMCP test fixtures
│   ├── test_main.py          # NetworkXMCP API tests
│   └── test_tools.py         # Analysis tools tests
├── run_tests.sh              # Test runner script
└── docker-compose.test.yml   # Docker test environment
```

## Running Tests

### Method 1: Using the Test Runner Script (Recommended)

```bash
# Run all tests
./run_tests.sh

# Run with options
./run_tests.sh --skip-integration  # Skip integration tests
./run_tests.sh --skip-api          # Skip API tests only
./run_tests.sh --skip-networkxmcp  # Skip NetworkXMCP tests only
./run_tests.sh --verbose           # Enable verbose output

# Get help
./run_tests.sh --help
```

### Method 2: Using Docker Compose

```bash
# Run tests in Docker environment
docker compose -f docker-compose.test.yml up --build

# Run specific service tests
docker compose -f docker-compose.test.yml up api-test
docker compose -f docker-compose.test.yml up networkxmcp-test
docker compose -f docker-compose.test.yml up integration-test

# Clean up test environment
docker compose -f docker-compose.test.yml down -v
```

### Method 3: Manual Execution

```bash
# Install test dependencies
cd API && pip install -e ".[test]"
cd NetworkXMCP && pip install -e ".[test]"

# Run API tests
cd API
pytest -v --cov=. --cov-report=term-missing --cov-report=html:htmlcov

# Run NetworkXMCP tests
cd NetworkXMCP
pytest -v --cov=. --cov-report=term-missing --cov-report=html:htmlcov

# Run specific test files
pytest test_auth.py -v
pytest test_network.py::test_upload_network_file -v
```

## Test Configuration

### Pytest Configuration

Both services use pytest with the following configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "6.0"
addopts = [
    "-ra",                      # Show all test outcomes
    "--strict-markers",         # Enforce marker definitions
    "--strict-config",          # Strict configuration validation
    "--cov=.",                  # Coverage for current directory
    "--cov-report=term-missing", # Show missing lines in terminal
    "--cov-report=html:htmlcov", # Generate HTML coverage report
    "--cov-report=xml",         # Generate XML coverage report
]
testpaths = ["tests", "."]
filterwarnings = [
    "ignore::UserWarning",
    "ignore::DeprecationWarning",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

### Test Markers

Use markers to categorize and selectively run tests:

```bash
# Run only unit tests
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration
```

## Test Dependencies

### API Service

- `pytest>=7.4.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-mock>=3.11.0` - Mocking utilities
- `pytest-cov>=4.1.0` - Coverage reporting
- `httpx[test]>=0.27.0` - HTTP test client

### NetworkXMCP Service

- Same as API service for consistency

## Test Coverage

### Coverage Reports

Tests generate multiple coverage report formats:

1. **Terminal Report**: Shows coverage percentage and missing lines
2. **HTML Report**: Interactive coverage report in `htmlcov/index.html`
3. **XML Report**: Machine-readable coverage data for CI/CD

### Coverage Configuration

Coverage settings in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["."]
omit = [
    "*/tests/*",
    "*/test_*",
    "*/__pycache__/*",
    "*/venv/*",
    "*/.venv/*",
    "*/conftest.py",
    "*/setup.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
```

## Test Fixtures

### API Fixtures (conftest.py)

- `client`: FastAPI test client
- `db_session`: Database session for testing
- `test_user`: Sample user for authentication tests
- `auth_headers`: Authentication headers with JWT token
- `sample_graphml`: Sample GraphML data for network tests

### NetworkXMCP Fixtures (conftest.py)

- `sample_graph`: NetworkX graph for testing
- `sample_graphml_content`: GraphML content for parsing tests
- `layout_params`: Parameters for layout algorithms

## Writing New Tests

### Test File Naming

- Test files must start with `test_` or end with `_test.py`
- Test functions must start with `test_`
- Test classes must start with `Test`

### Example Test Structure

```python
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

class TestFeature:
    """Test class for a specific feature."""

    def test_basic_functionality(self, client: TestClient):
        """Test basic functionality."""
        response = client.get("/endpoint")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @pytest.mark.asyncio
    async def test_async_functionality(self, async_client: AsyncClient):
        """Test async functionality."""
        response = await async_client.get("/async-endpoint")
        assert response.status_code == 200

    @pytest.mark.slow
    def test_slow_operation(self, client: TestClient):
        """Test that takes longer to run."""
        # Test implementation
        pass

    @pytest.mark.integration
    def test_service_integration(self, client: TestClient):
        """Test integration between services."""
        # Test implementation
        pass
```

### Authentication in Tests

```python
def test_protected_endpoint(self, client: TestClient, auth_headers: dict):
    """Test endpoint that requires authentication."""
    response = client.get("/protected", headers=auth_headers)
    assert response.status_code == 200

def test_unauthorized_access(self, client: TestClient):
    """Test unauthorized access to protected endpoint."""
    response = client.get("/protected")
    assert response.status_code == 401
```

### Database Testing

```python
def test_database_operation(self, db_session):
    """Test database operations."""
    # Create test data
    user = User(username="test", email="test@example.com")
    db_session.add(user)
    db_session.commit()

    # Test query
    retrieved_user = db_session.query(User).filter_by(username="test").first()
    assert retrieved_user is not None
    assert retrieved_user.email == "test@example.com"
```

### Mocking External Services

```python
def test_external_api_call(self, client: TestClient, mocker):
    """Test API call with mocked external service."""
    # Mock external service
    mock_response = {"result": "success"}
    mocker.patch("services.external_api.call_service", return_value=mock_response)

    # Test endpoint
    response = client.post("/process", json={"data": "test"})
    assert response.status_code == 200
    assert response.json() == mock_response
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          cd API && pip install -e ".[test]"
          cd NetworkXMCP && pip install -e ".[test]"

      - name: Run tests
        run: ./run_tests.sh

      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          files: ./API/coverage.xml,./NetworkXMCP/coverage.xml
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure test dependencies are installed

   ```bash
   pip install -e ".[test]"
   ```

2. **Database Connection Issues**: Check database URL in test environment

   ```python
   # In conftest.py
   SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
   ```

3. **Service Communication Failures**: Ensure services are running for integration tests

   ```bash
   docker compose up -d
   ```

4. **Authentication Failures**: Verify JWT token generation in tests
   ```python
   # Check token creation in conftest.py
   token = create_access_token(data={"sub": user.username})
   ```

### Debug Mode

Run tests with additional debugging:

```bash
# Verbose output with print statements
pytest -v -s

# Debug specific test
pytest test_auth.py::test_login -v -s --tb=long

# Run with pdb debugger
pytest --pdb test_file.py
```

### Performance Testing

For performance testing, use the `slow` marker:

```python
@pytest.mark.slow
def test_large_network_processing(self, client: TestClient):
    """Test processing of large networks."""
    # Generate large network data
    # Test performance metrics
    pass
```

Run performance tests separately:

```bash
pytest -m slow --durations=10
```

## Best Practices

1. **Test Independence**: Each test should be independent and not rely on other tests
2. **Use Fixtures**: Leverage pytest fixtures for setup and teardown
3. **Mock External Services**: Use mocking for external API calls
4. **Test Edge Cases**: Include tests for error conditions and edge cases
5. **Keep Tests Fast**: Use the `slow` marker for time-consuming tests
6. **Clear Assertions**: Write clear, descriptive assertion messages
7. **Test Documentation**: Document complex test scenarios

## Integration with Development Workflow

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Add to .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: ./run_tests.sh
        language: system
        types: [python]
        stages: [commit]
```

### Development Commands

```bash
# Quick test during development
pytest test_specific_feature.py -x -v

# Test with coverage on changed files
pytest --cov=changed_module test_changed_module.py

# Watch mode for continuous testing
pytest-watch -- -x -v
```

This comprehensive test suite ensures the reliability and maintainability of the LLMGraphvis project while following FastAPI testing best practices.
