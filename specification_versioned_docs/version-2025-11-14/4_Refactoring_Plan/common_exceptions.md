# 共通例外クラス階層設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトで使用する共通例外クラス階層の設計について説明します。例外クラスを統一することで、エラーハンドリングの一貫性を確保し、デバッグやエラー報告を容易にします。

## 設計目標

1. **一貫性**: API側とNetworkXMCP側で一貫したエラーハンドリングを提供する
2. **詳細な情報**: エラーの原因と解決策に関する詳細な情報を提供する
3. **コンテキスト**: エラーが発生した状況に関する情報を含める
4. **拡張性**: 新しいエラータイプを容易に追加できるようにする
5. **互換性**: FastAPIのエラーハンドリングと互換性を持つ

## 例外クラス階層

```
BaseError
├── ValidationError
│   ├── SchemaValidationError
│   ├── DataValidationError
│   └── GraphMLValidationError
├── ProcessingError
│   ├── GraphProcessingError
│   ├── LayoutProcessingError
│   └── CentralityProcessingError
├── CommunicationError
│   ├── MCPCommunicationError
│   ├── DatabaseCommunicationError
│   └── LLMCommunicationError
├── AuthenticationError
│   ├── InvalidCredentialsError
│   ├── TokenExpiredError
│   └── PermissionDeniedError
└── ResourceError
    ├── ResourceNotFoundError
    ├── ResourceConflictError
    └── ResourceLimitExceededError
```

## 基本例外クラス

### BaseError

すべての例外の基底クラスです。基本的なエラー情報を提供します。

**属性**:
- `message`: エラーメッセージ
- `error_code`: エラーコード
- `status_code`: HTTPステータスコード
- `context`: エラーコンテキスト情報
- `timestamp`: エラー発生時刻

**実装例**:
```python
from datetime import datetime
from typing import Dict, Any, Optional

class BaseError(Exception):
    """すべての例外の基底クラス。"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.context = context or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """例外をディクショナリに変換する。"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }
```

## 検証エラー

### ValidationError

入力データの検証に関連するエラーの基底クラスです。

**属性**:
- `validation_errors`: 検証エラーのリスト

**実装例**:
```python
from typing import List, Dict, Any, Optional

class ValidationError(BaseError):
    """入力データの検証に関連するエラーの基底クラス。"""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        error_code: str = "VALIDATION_ERROR",
        status_code: int = 400,
        context: Optional[Dict[str, Any]] = None
    ):
        self.validation_errors = validation_errors or []
        super().__init__(message, error_code, status_code, context)
    
    def to_dict(self) -> Dict[str, Any]:
        """例外をディクショナリに変換する。"""
        result = super().to_dict()
        result["validation_errors"] = self.validation_errors
        return result
```

### SchemaValidationError

スキーマ検証に失敗した場合に発生するエラーです。

**実装例**:
```python
class SchemaValidationError(ValidationError):
    """スキーマ検証に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            validation_errors,
            error_code="SCHEMA_VALIDATION_ERROR",
            status_code=400,
            context=context
        )
```

### DataValidationError

データ検証に失敗した場合に発生するエラーです。

**実装例**:
```python
class DataValidationError(ValidationError):
    """データ検証に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            validation_errors,
            error_code="DATA_VALIDATION_ERROR",
            status_code=400,
            context=context
        )
```

### GraphMLValidationError

GraphML検証に失敗した場合に発生するエラーです。

**実装例**:
```python
class GraphMLValidationError(ValidationError):
    """GraphML検証に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            validation_errors,
            error_code="GRAPHML_VALIDATION_ERROR",
            status_code=400,
            context=context
        )
```

## 処理エラー

### ProcessingError

データ処理に関連するエラーの基底クラスです。

**実装例**:
```python
class ProcessingError(BaseError):
    """データ処理に関連するエラーの基底クラス。"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "PROCESSING_ERROR",
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, status_code, context)
```

### GraphProcessingError

グラフ処理に失敗した場合に発生するエラーです。

**実装例**:
```python
class GraphProcessingError(ProcessingError):
    """グラフ処理に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code="GRAPH_PROCESSING_ERROR",
            status_code=500,
            context=context
        )
```

### LayoutProcessingError

レイアウト処理に失敗した場合に発生するエラーです。

**実装例**:
```python
class LayoutProcessingError(ProcessingError):
    """レイアウト処理に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code="LAYOUT_PROCESSING_ERROR",
            status_code=500,
            context=context
        )
```

### CentralityProcessingError

中心性計算に失敗した場合に発生するエラーです。

**実装例**:
```python
class CentralityProcessingError(ProcessingError):
    """中心性計算に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code="CENTRALITY_PROCESSING_ERROR",
            status_code=500,
            context=context
        )
```

## 通信エラー

### CommunicationError

外部サービスとの通信に関連するエラーの基底クラスです。

**属性**:
- `service_name`: 通信先のサービス名

**実装例**:
```python
class CommunicationError(BaseError):
    """外部サービスとの通信に関連するエラーの基底クラス。"""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        error_code: str = "COMMUNICATION_ERROR",
        status_code: int = 502,
        context: Optional[Dict[str, Any]] = None
    ):
        self.service_name = service_name
        context = context or {}
        context["service_name"] = service_name
        super().__init__(message, error_code, status_code, context)
```

### MCPCommunicationError

MCP通信に失敗した場合に発生するエラーです。

**実装例**:
```python
class MCPCommunicationError(CommunicationError):
    """MCP通信に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            service_name="NetworkXMCP",
            error_code="MCP_COMMUNICATION_ERROR",
            status_code=502,
            context=context
        )
```

### DatabaseCommunicationError

データベース通信に失敗した場合に発生するエラーです。

**実装例**:
```python
class DatabaseCommunicationError(CommunicationError):
    """データベース通信に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            service_name="Database",
            error_code="DATABASE_COMMUNICATION_ERROR",
            status_code=503,
            context=context
        )
```

### LLMCommunicationError

LLM通信に失敗した場合に発生するエラーです。

**実装例**:
```python
class LLMCommunicationError(CommunicationError):
    """LLM通信に失敗した場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            service_name="LLM",
            error_code="LLM_COMMUNICATION_ERROR",
            status_code=502,
            context=context
        )
```

## 認証エラー

### AuthenticationError

認証に関連するエラーの基底クラスです。

**実装例**:
```python
class AuthenticationError(BaseError):
    """認証に関連するエラーの基底クラス。"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "AUTHENTICATION_ERROR",
        status_code: int = 401,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, status_code, context)
```

### InvalidCredentialsError

認証情報が無効な場合に発生するエラーです。

**実装例**:
```python
class InvalidCredentialsError(AuthenticationError):
    """認証情報が無効な場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str = "Invalid credentials",
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code="INVALID_CREDENTIALS_ERROR",
            status_code=401,
            context=context
        )
```

### TokenExpiredError

トークンが期限切れの場合に発生するエラーです。

**実装例**:
```python
class TokenExpiredError(AuthenticationError):
    """トークンが期限切れの場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str = "Token has expired",
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code="TOKEN_EXPIRED_ERROR",
            status_code=401,
            context=context
        )
```

### PermissionDeniedError

権限がない場合に発生するエラーです。

**実装例**:
```python
class PermissionDeniedError(AuthenticationError):
    """権限がない場合に発生するエラー。"""
    
    def __init__(
        self,
        message: str = "Permission denied",
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code="PERMISSION_DENIED_ERROR",
            status_code=403,
            context=context
        )
```

## リソースエラー

### ResourceError

リソースに関連するエラーの基底クラスです。

**属性**:
- `resource_type`: リソースの種類
- `resource_id`: リソースのID

**実装例**:
```python
class ResourceError(BaseError):
    """リソースに関連するエラーの基底クラス。"""
    
    def __init__(
        self,
        message: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        error_code: str = "RESOURCE_ERROR",
        status_code: int = 404,
        context: Optional[Dict[str, Any]] = None
    ):
        self.resource_type = resource_type
        self.resource_id = resource_id
        context = context or {}
        context["resource_type"] = resource_type
        if resource_id:
            context["resource_id"] = resource_id
        super().__init__(message, error_code, status_code, context)
```

### ResourceNotFoundError

リソースが見つからない場合に発生するエラーです。

**実装例**:
```python
class ResourceNotFoundError(ResourceError):
    """リソースが見つからない場合に発生するエラー。"""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            if resource_id:
                message = f"{resource_type} with ID {resource_id} not found"
            else:
                message = f"{resource_type} not found"
        super().__init__(
            message,
            resource_type,
            resource_id,
            error_code="RESOURCE_NOT_FOUND_ERROR",
            status_code=404,
            context=context
        )
```

### ResourceConflictError

リソースの競合が発生した場合に発生するエラーです。

**実装例**:
```python
class ResourceConflictError(ResourceError):
    """リソースの競合が発生した場合に発生するエラー。"""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            if resource_id:
                message = f"Conflict with {resource_type} with ID {resource_id}"
            else:
                message = f"Conflict with {resource_type}"
        super().__init__(
            message,
            resource_type,
            resource_id,
            error_code="RESOURCE_CONFLICT_ERROR",
            status_code=409,
            context=context
        )
```

### ResourceLimitExceededError

リソースの制限を超えた場合に発生するエラーです。

**実装例**:
```python
class ResourceLimitExceededError(ResourceError):
    """リソースの制限を超えた場合に発生するエラー。"""
    
    def __init__(
        self,
        resource_type: str,
        limit: int,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"{resource_type} limit of {limit} exceeded"
        context = context or {}
        context["limit"] = limit
        super().__init__(
            message,
            resource_type,
            None,
            error_code="RESOURCE_LIMIT_EXCEEDED_ERROR",
            status_code=429,
            context=context
        )
```

## エラーコード一覧

| エラーコード | 説明 | HTTPステータスコード |
|------------|------|-------------------|
| `UNKNOWN_ERROR` | 不明なエラー | 500 |
| `VALIDATION_ERROR` | 検証エラー | 400 |
| `SCHEMA_VALIDATION_ERROR` | スキーマ検証エラー | 400 |
| `DATA_VALIDATION_ERROR` | データ検証エラー | 400 |
| `GRAPHML_VALIDATION_ERROR` | GraphML検証エラー | 400 |
| `PROCESSING_ERROR` | 処理エラー | 500 |
| `GRAPH_PROCESSING_ERROR` | グラフ処理エラー | 500 |
| `LAYOUT_PROCESSING_ERROR` | レイアウト処理エラー | 500 |
| `CENTRALITY_PROCESSING_ERROR` | 中心性計算エラー | 500 |
| `COMMUNICATION_ERROR` | 通信エラー | 502 |
| `MCP_COMMUNICATION_ERROR` | MCP通信エラー | 502 |
| `DATABASE_COMMUNICATION_ERROR` | データベース通信エラー | 503 |
| `LLM_COMMUNICATION_ERROR` | LLM通信エラー | 502 |
| `AUTHENTICATION_ERROR` | 認証エラー | 401 |
| `INVALID_CREDENTIALS_ERROR` | 無効な認証情報エラー | 401 |
| `TOKEN_EXPIRED_ERROR` | トークン期限切れエラー | 401 |
| `PERMISSION_DENIED_ERROR` | 権限拒否エラー | 403 |
| `RESOURCE_ERROR` | リソースエラー | 404 |
| `RESOURCE_NOT_FOUND_ERROR` | リソース未検出エラー | 404 |
| `RESOURCE_CONFLICT_ERROR` | リソース競合エラー | 409 |
| `RESOURCE_LIMIT_EXCEEDED_ERROR` | リソース制限超過エラー | 429 |

## FastAPIとの統合

FastAPIでは、例外ハンドラーを使用して例外をキャッチし、適切なレスポンスを返すことができます。以下は、FastAPIと統合する例です。

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from common.exceptions import BaseError

app = FastAPI()

@app.exception_handler(BaseError)
async def base_error_handler(request: Request, exc: BaseError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )
```

## 使用例

```python
from common.exceptions import ResourceNotFoundError, GraphMLValidationError

# リソースが見つからない場合
def get_network(network_id: int):
    network = db.query(Network).filter(Network.id == network_id).first()
    if not network:
        raise ResourceNotFoundError(
            resource_type="Network",
            resource_id=str(network_id)
        )
    return network

# GraphML検証エラーの場合
def validate_graphml(graphml_content: str):
    errors = []
    if "<graph" not in graphml_content:
        errors.append({
            "field": "graphml_content",
            "error": "Missing <graph> element"
        })
    if errors:
        raise GraphMLValidationError(
            message="Invalid GraphML content",
            validation_errors=errors,
            context={"content_length": len(graphml_content)}
        )
    return True
```

## まとめ

共通例外クラス階層を設計することで、以下のメリットが得られます：

1. エラーハンドリングの一貫性
2. 詳細なエラー情報の提供
3. エラーコンテキストの追加
4. 拡張性の確保
5. FastAPIとの互換性

この設計を実装することで、LLMGraphvisプロジェクト全体でエラーハンドリングが統一され、デバッグやエラー報告が容易になります。