# エラーハンドリング統一設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトのエラーハンドリング統一設計について説明します。現在、API側とNetworkXMCP側でエラーハンドリングが統一されておらず、エラーレスポンスの形式も不統一です。共通例外クラス階層を活用し、一貫したエラーハンドリングとレスポンス形式を提供することを目的としています。

## 現状の課題

1. **エラーハンドリングの不統一**: API側とNetworkXMCP側でエラーハンドリング方法が異なる
2. **例外クラスの不統一**: 異なる例外クラスが使用されている
3. **エラーレスポンスの不統一**: エラーレスポンスの形式が統一されていない
4. **エラー情報の不足**: エラーコンテキスト情報が不足している

## 設計目標

1. **一貫性**: API側とNetworkXMCP側で一貫したエラーハンドリングを提供する
2. **詳細な情報**: エラーの原因と解決策に関する詳細な情報を提供する
3. **コンテキスト**: エラーが発生した状況に関する情報を含める
4. **拡張性**: 新しいエラータイプを容易に追加できるようにする
5. **互換性**: FastAPIのエラーハンドリングと互換性を持つ

## エラーハンドリング統一設計

### 1. API側のエラーハンドリング統一

#### 1.1 エラーハンドラーの実装

```python
# API/core/errors.py

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Dict, Any, List, Optional, Union, Type
import traceback
from datetime import datetime

from common.exceptions import (
    BaseError, ValidationError, ProcessingError, CommunicationError,
    AuthenticationError, ResourceError
)
from common.logging.config import get_logger

logger = get_logger("api.core.errors")

async def base_error_handler(request: Request, exc: BaseError) -> JSONResponse:
    """
    共通例外クラスのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"BaseError: {exc.message}", exc_info=True)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "context": exc.context,
            "timestamp": exc.timestamp.isoformat()
        }
    )

async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    検証エラーのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"ValidationError: {exc.message}", exc_info=True)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "validation_errors": exc.validation_errors,
            "context": exc.context,
            "timestamp": exc.timestamp.isoformat()
        }
    )

async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    FastAPIのリクエスト検証エラーのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"RequestValidationError: {str(exc)}")
    
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error_code": "REQUEST_VALIDATION_ERROR",
            "message": "Request validation error",
            "validation_errors": validation_errors,
            "context": {"path": request.url.path},
            "timestamp": datetime.now().isoformat()
        }
    )

async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    HTTPExceptionのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"HTTPException: {str(exc)}")
    
    status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = getattr(exc, "detail", str(exc))
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": "HTTP_ERROR",
            "message": detail,
            "context": {"path": request.url.path},
            "timestamp": datetime.now().isoformat()
        }
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    一般的な例外のエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "context": {
                "path": request.url.path,
                "error": str(exc)
            },
            "timestamp": datetime.now().isoformat()
        }
    )

def register_exception_handlers(app):
    """
    アプリケーションに例外ハンドラーを登録します。
    
    Args:
        app: FastAPIアプリケーション
    """
    # 共通例外クラス
    app.add_exception_handler(BaseError, base_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(ProcessingError, base_error_handler)
    app.add_exception_handler(CommunicationError, base_error_handler)
    app.add_exception_handler(AuthenticationError, base_error_handler)
    app.add_exception_handler(ResourceError, base_error_handler)
    
    # FastAPIの例外
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    
    # 一般的な例外
    app.add_exception_handler(Exception, general_exception_handler)
```

#### 1.2 エラーハンドラーの登録

```python
# API/main.py

from fastapi import FastAPI
from core.errors import register_exception_handlers
from common.logging.config import configure_logging

# ロギングの設定
configure_logging()

app = FastAPI(
    title="LLMGraphvis API",
    description="API for LLMGraphvis",
    version="0.1.0",
)

# 例外ハンドラーの登録
register_exception_handlers(app)

# ルーターの登録
# ...
```

#### 1.3 例外の使用例

```python
# API/routers/network/upload.py

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from typing import Dict, Any

import models
import auth
from database import get_db
from services import mcp_client
from common.exceptions import (
    GraphMLValidationError, GraphProcessingError, MCPCommunicationError,
    ResourceNotFoundError, PermissionDeniedError
)
from common.logging.config import get_logger

logger = get_logger("api.routers.network.upload")

router = APIRouter()

@router.post("/upload", response_model=Dict[str, int])
async def upload_new_network(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    GraphMLファイルから新しいネットワークをアップロードします。
    
    Args:
        file: アップロードするGraphMLファイル
        current_user: 現在の認証済みユーザー
        db: データベースセッション
        
    Returns:
        新しい会話とネットワークのIDを含む辞書
    """
    if not file.filename.endswith(".graphml"):
        raise GraphMLValidationError(
            message="Invalid file type. Please upload a .graphml file.",
            validation_errors=[{"error": "Invalid file extension"}]
        )
    
    try:
        # ファイルの読み込み
        graphml_content_bytes = await file.read()
        graphml_content_str = graphml_content_bytes.decode("utf-8")
        
        # NetworkXMCPを呼び出してGraphMLを変換/正規化
        try:
            result = await mcp_client.convert_graphml(graphml_content_str)
            normalized_graphml_str = result.get("graphml_content", "")
            logger.info(f"Normalized GraphML length: {len(normalized_graphml_str)}")
        except mcp_client.MCPError as e:
            logger.error(f"Error from NetworkXMCP: {e.message}")
            raise MCPCommunicationError(
                message=e.message,
                service_name="NetworkXMCP",
                status_code=e.status_code,
                context={"file_name": file.filename}
            )
        
        # 新しい会話の作成
        db_conversation = models.Conversation(
            title=f"Conversation for {file.filename}",
            user_id=current_user.id
        )
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)
        
        # 関連するネットワークを正規化されたコンテンツで作成
        db_network = models.Network(
            name=file.filename,
            conversation_id=db_conversation.id,
            graphml_content=normalized_graphml_str
        )
        db.add(db_network)
        db.commit()
        db.refresh(db_network)
        
        # ネットワークのデフォルトレイアウト（spring）を計算
        try:
            await mcp_client.change_layout(db_network.id, "spring")
            logger.info(f"Applied default spring layout to network {db_network.id}")
        except mcp_client.MCPError as e:
            # エラーをログに記録するが、アップロードは失敗させない
            logger.error(f"Error applying default layout: {e.message}")
        
        return {"conversation_id": db_conversation.id, "network_id": db_network.id}
    
    except (GraphMLValidationError, MCPCommunicationError) as e:
        # 既知の例外は再送
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in upload_new_network: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"An unexpected error occurred: {str(e)}",
            context={"file_name": file.filename}
        )
```

### 2. NetworkXMCP側のエラーハンドリング統一

#### 2.1 エラーハンドラーの実装

```python
# NetworkXMCP/core/errors.py

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Dict, Any, List, Optional, Union, Type
import traceback
from datetime import datetime

from common.exceptions import (
    BaseError, ValidationError, ProcessingError, CommunicationError,
    AuthenticationError, ResourceError
)
from common.logging.config import get_logger

logger = get_logger("networkx_mcp.core.errors")

async def base_error_handler(request: Request, exc: BaseError) -> JSONResponse:
    """
    共通例外クラスのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"BaseError: {exc.message}", exc_info=True)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "context": exc.context,
            "timestamp": exc.timestamp.isoformat()
        }
    )

async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    検証エラーのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"ValidationError: {exc.message}", exc_info=True)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "validation_errors": exc.validation_errors,
            "context": exc.context,
            "timestamp": exc.timestamp.isoformat()
        }
    )

async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    FastAPIのリクエスト検証エラーのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"RequestValidationError: {str(exc)}")
    
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error_code": "REQUEST_VALIDATION_ERROR",
            "message": "Request validation error",
            "validation_errors": validation_errors,
            "context": {"path": request.url.path},
            "timestamp": datetime.now().isoformat()
        }
    )

async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    HTTPExceptionのエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"HTTPException: {str(exc)}")
    
    status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = getattr(exc, "detail", str(exc))
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": "HTTP_ERROR",
            "message": detail,
            "context": {"path": request.url.path},
            "timestamp": datetime.now().isoformat()
        }
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    一般的な例外のエラーハンドラー。
    
    Args:
        request: リクエスト
        exc: 例外
        
    Returns:
        JSONResponse: エラーレスポンス
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "context": {
                "path": request.url.path,
                "error": str(exc)
            },
            "timestamp": datetime.now().isoformat()
        }
    )

def register_exception_handlers(app):
    """
    アプリケーションに例外ハンドラーを登録します。
    
    Args:
        app: FastAPIアプリケーション
    """
    # 共通例外クラス
    app.add_exception_handler(BaseError, base_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(ProcessingError, base_error_handler)
    app.add_exception_handler(CommunicationError, base_error_handler)
    app.add_exception_handler(AuthenticationError, base_error_handler)
    app.add_exception_handler(ResourceError, base_error_handler)
    
    # FastAPIの例外
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    
    # 一般的な例外
    app.add_exception_handler(Exception, general_exception_handler)
```

#### 2.2 エラーハンドラーの登録

```python
# NetworkXMCP/main.py

from fastapi import FastAPI
from core.errors import register_exception_handlers
from common.logging.config import configure_logging
from database.session import init_db

# ロギングの設定
configure_logging()

app = FastAPI(
    title="NetworkX MCP (Stateful)",
    description="Stateful MCP server for network analysis with caching.",
    version="0.3.0",
)

# 例外ハンドラーの登録
register_exception_handlers(app)

# データベースの初期化
@app.on_event("startup")
async def startup_event():
    init_db()

# ルーターの登録
# ...
```

#### 2.3 例外の使用例

```python
# NetworkXMCP/api/layout.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from database.session import get_db
from database.operations import get_network, update_layout_cache, get_layout_cache
from layouts.layout_functions import get_layout_function
from common.exceptions import (
    ResourceNotFoundError, GraphProcessingError, DatabaseCommunicationError
)
from common.logging.config import get_logger
from common.models.network import LayoutRequest, LayoutResponse

logger = get_logger("networkx_mcp.api.layout")

router = APIRouter()

@router.post("/tools/change_layout", response_model=Dict[str, Any])
async def api_change_layout(params: LayoutRequest, db: Session = Depends(get_db)):
    """
    ネットワークのレイアウトを変更します。
    
    Args:
        params: レイアウトパラメータ
        db: データベースセッション
        
    Returns:
        レイアウト変更操作の結果
    """
    try:
        # キャッシュをチェック
        cached_positions = get_layout_cache(db, params.network_id, params.layout_type)
        if cached_positions:
            logger.info(f"Cache hit for layout '{params.layout_type}' on network {params.network_id}")
            return {
                "result": {
                    "success": True,
                    "layout_type": params.layout_type,
                    "positions": cached_positions
                }
            }
        
        logger.info(f"Cache miss for layout '{params.layout_type}'. Calculating...")
        
        # ネットワークを取得
        network = get_network(db, params.network_id)
        
        # レイアウト関数を取得
        layout_func = get_layout_function(params.layout_type)
        
        # GraphMLをパース
        import networkx as nx
        import io
        content_io = io.StringIO(network.graphml_content)
        G = nx.read_graphml(content_io)
        
        # レイアウトを計算
        try:
            positions = layout_func(G, **params.layout_params)
        except Exception as e:
            logger.error(f"Error calculating layout: {e}", exc_info=True)
            raise GraphProcessingError(
                message=f"Error calculating layout: {str(e)}",
                context={"network_id": params.network_id, "layout_type": params.layout_type}
            )
        
        # 位置情報をノード属性として設定
        for node, pos in positions.items():
            G.nodes[node]['x'] = str(float(pos[0]))
            G.nodes[node]['y'] = str(float(pos[1]))
        
        # 更新されたGraphMLを生成
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        updated_graphml = output.read().decode("utf-8")
        
        # 位置情報を辞書形式でも返す
        positions_dict = {
            str(node): {"x": float(pos[0]), "y": float(pos[1])}
            for node, pos in positions.items()
        }
        
        # データベースを更新
        network.graphml_content = updated_graphml
        update_layout_cache(db, params.network_id, params.layout_type, positions_dict)
        
        logger.info(f"Successfully calculated {params.layout_type} layout for network {params.network_id}")
        
        return {
            "result": {
                "success": True,
                "layout_type": params.layout_type,
                "positions": positions_dict
            }
        }
    
    except (ResourceNotFoundError, GraphProcessingError, DatabaseCommunicationError) as e:
        # 既知の例外は再送
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in api_change_layout: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"An unexpected error occurred: {str(e)}",
            context={"network_id": params.network_id, "layout_type": params.layout_type}
        )
```

### 3. エラーレスポンス形式の標準化

#### 3.1 標準エラーレスポンスモデル

```python
# common/models/errors.py

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime

class ValidationErrorItem(BaseModel):
    """
    検証エラー項目モデル。
    """
    loc: Optional[List[str]] = None
    msg: str
    type: Optional[str] = None
    field: Optional[str] = None
    error: Optional[str] = None

class ErrorResponse(BaseModel):
    """
    エラーレスポンスモデル。
    """
    success: bool = False
    error_code: str
    message: str
    validation_errors: Optional[List[ValidationErrorItem]] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = {
        "from_attributes": True
    }
```

#### 3.2 エラーレスポンスの使用例

```python
# API/routers/network/utils.py

from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

import models
from common.exceptions import ResourceNotFoundError, PermissionDeniedError
from common.logging.config import get_logger

logger = get_logger("api.routers.network.utils")

def get_network_for_user(db: Session, network_id: int, user_id: int) -> models.Network:
    """
    ユーザーのネットワークを取得し、所有権を確認します。
    
    Args:
        db: データベースセッション
        network_id: 取得するネットワークのID
        user_id: リクエストしているユーザーのID
        
    Returns:
        ネットワークオブジェクト
        
    Raises:
        ResourceNotFoundError: ネットワークが見つからない場合
        PermissionDeniedError: ユーザーがネットワークにアクセスする権限がない場合
    """
    db_network = db.query(models.Network).filter(
        models.Network.id == network_id
    ).first()

    if not db_network:
        logger.warning(f"Network {network_id} not found")
        raise ResourceNotFoundError(
            resource_type="Network",
            resource_id=str(network_id),
            message="Network not found"
        )

    # ネットワークの会話が現在のユーザーに属しているか確認
    if db_network.conversation.user_id != user_id:
        logger.warning(f"User {user_id} not authorized to access network {network_id}")
        raise PermissionDeniedError(
            message="Not authorized to access this network",
            context={"network_id": network_id, "user_id": user_id}
        )
        
    return db_network
```

## 移行計画

1. **共通例外クラスの導入**:
   - 共通例外クラスを `common/exceptions/` ディレクトリに実装
   - 既存の例外を共通例外クラスに置き換え

2. **エラーハンドラーの実装**:
   - API側とNetworkXMCP側にエラーハンドラーを実装
   - アプリケーションに例外ハンドラーを登録

3. **エラーレスポンス形式の標準化**:
   - 標準エラーレスポンスモデルを実装
   - すべてのエンドポイントで標準エラーレスポンスを使用

4. **既存コードの更新**:
   - HTTPExceptionを共通例外クラスに置き換え
   - エラーメッセージとコンテキスト情報を追加

## 期待される効果

1. **一貫したエラーハンドリング**: API側とNetworkXMCP側で一貫したエラーハンドリングが提供される
2. **詳細なエラー情報**: エラーの原因と解決策に関する詳細な情報が提供される
3. **コンテキスト情報の追加**: エラーが発生した状況に関する情報が含まれる
4. **拡張性の向上**: 新しいエラータイプを容易に追加できる
5. **デバッグの容易化**: 詳細なエラー情報によりデバッグが容易になる