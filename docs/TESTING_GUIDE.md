# LLMGraphvis Testing Guide

このガイドでは、API、NetworkXMCP、フロントエンドサービスを含むLLMGraphvisプロジェクトのテストスイートの実行と維持管理について包括的な情報を提供します。

## 概要

テストスイートは[FastAPI公式テストチュートリアル](https://fastapi.tiangolo.com/tutorial/testing/)に基づいて構築されており、以下を含みます：

- **単体テスト**: 個別コンポーネントのテスト
- **統合テスト**: サービス間通信のテスト
- **APIエンドポイントテスト**: 認証機能付き
- **ネットワーク分析テスト**: グラフ操作のテスト
- **LLM統合テスト**: Google Gemini/OpenAI統合のテスト
- **カバレッジレポート**: コード品質メトリクス

## テスト構造

```
├── API/
│   ├── conftest.py           # テストフィクスチャーと設定
│   ├── test_auth.py          # 認証機能のテスト
│   ├── test_network.py       # ネットワーク操作のテスト
│   ├── test_chat.py          # チャット機能のテスト（LLM統合）
│   ├── test_main.py          # メインアプリケーションのテスト
│   └── test_integration.py   # API-NetworkXMCP統合テスト
├── NetworkXMCP/
│   ├── conftest.py           # NetworkXMCPテストフィクスチャー
│   ├── test_main.py          # NetworkXMCP APIのテスト
│   ├── test_tools.py         # 分析ツールのテスト
│   └── test_new_features.py  # FastMCP 2.0機能のテスト
├── frontend/
│   ├── src/tests/            # Reactコンポーネントのテスト
│   └── vitest.config.js      # Viteテスト設定
├── run_tests.sh              # テスト実行スクリプト
└── docker-compose.test.yml   # Dockerテスト環境
```

## テストの実行

### 方法1: テストランナースクリプトの使用（推奨）

```bash
# すべてのテストを実行
./run_tests.sh

# オプション付きで実行
./run_tests.sh --skip-integration  # 統合テストをスキップ
./run_tests.sh --skip-api          # APIテストのみスキップ
./run_tests.sh --skip-networkxmcp  # NetworkXMCPテストのみスキップ
./run_tests.sh --skip-frontend     # フロントエンドテストをスキップ
./run_tests.sh --verbose           # 詳細出力を有効化

# ヘルプの表示
./run_tests.sh --help
```

### 方法2: Docker Composeの使用

```bash
# Docker環境でテストを実行
docker compose -f docker-compose.test.yml up --build

# 特定のサービステストを実行
docker compose -f docker-compose.test.yml up api-test
docker compose -f docker-compose.test.yml up networkxmcp-test
docker compose -f docker-compose.test.yml up frontend-test
docker compose -f docker-compose.test.yml up integration-test

# テスト環境のクリーンアップ
docker compose -f docker-compose.test.yml down -v
```

### 方法3: 手動実行

```bash
# テスト依存関係をインストール
cd API && pip install -e ".[test]"
cd NetworkXMCP && pip install -e ".[test]"
cd frontend && npm install

# APIテストを実行
cd API
pytest -v --cov=. --cov-report=term-missing --cov-report=html:htmlcov

# NetworkXMCPテストを実行
cd NetworkXMCP
pytest -v --cov=. --cov-report=term-missing --cov-report=html:htmlcov

# フロントエンドテストを実行
cd frontend
npm test

# 特定のテストファイルを実行
pytest test_auth.py -v
pytest test_network.py::test_upload_network_file -v
npm test -- auth.test.jsx
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

## テスト依存関係

### APIサービス

- `pytest>=7.4.0` - テスティングフレームワーク
- `pytest-asyncio>=0.21.0` - 非同期テストサポート
- `pytest-mock>=3.11.0` - モッキングユーティリティ
- `pytest-cov>=4.1.0` - カバレッジレポート
- `httpx[test]>=0.27.0` - HTTPテストクライアント

### NetworkXMCPサービス

- 一貫性のためAPIサービスと同じ依存関係

### フロントエンドサービス

- `vitest>=1.0.0` - Viteテスティングフレームワーク
- `@testing-library/react>=13.0.0` - Reactテストユーティリティ
- `@testing-library/jest-dom>=6.0.0` - 追加のマッチャー
- `jsdom>=22.0.0` - DOM環境のシミュレーション

## 新機能のテスト

### FastMCP 2.0統合テスト

NetworkXMCPサービスでは、FastMCP 2.0フレームワークの統合をテストします：

```python
# NetworkXMCP/test_new_features.py
def test_fastmcp_openapi_integration():
    """OpenAPI仕様からMCPツールが正しく生成されることを確認"""
    # テスト実装

def test_mcp_tool_availability():
    """すべてのAPIエンドポイントがMCPツールとして利用可能であることを確認"""
    # テスト実装
```

### LLM統合テスト

```python
# API/test_chat.py
def test_google_gemini_integration():
    """Google Gemini統合のテスト"""
    # モック実装

def test_openai_integration():
    """OpenAI統合のテスト"""
    # モック実装

def test_layout_recommendation():
    """レイアウト推薦機能のテスト"""
    # テスト実装
```

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
