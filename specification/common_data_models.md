# 共通データモデル定義設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトで使用する共通データモデル定義の設計について説明します。現在、API側とNetworkXMCP側で重複しているデータモデル定義を共通モジュールに抽出し、再利用性を高めることを目的としています。

## 現状の課題

1. **モデルの重複**: API側とNetworkXMCP側で類似のデータモデルが重複している
2. **一貫性の欠如**: モデル定義や属性名が統一されていない
3. **機能拡張の困難**: モデル変更時に複数の場所を修正する必要がある
4. **依存関係の複雑さ**: モデル間の依存関係が不明確

## 設計目標

1. **再利用性**: 共通のデータモデル定義を提供する
2. **一貫性**: 統一された命名規則と属性定義を提供する
3. **拡張性**: 新しい属性や関連を容易に追加できるようにする
4. **分離**: データベースモデルとAPIスキーマを明確に分離する
5. **型安全性**: 型ヒントを活用し、開発時のエラー検出を容易にする

## モジュール構造

```
common/
  models/
    __init__.py        # モジュールのエクスポート
    base.py            # 基本モデル定義
    network.py         # ネットワーク関連モデル
    conversation.py    # 会話関連モデル
    user.py            # ユーザー関連モデル
    graphml.py         # GraphML関連モデル
    types.py           # 共通型定義
```

## 主要コンポーネント

### 1. 基本モデル (base.py)

基本的なモデル定義を提供します。

```python
# common/models/base.py

from datetime import datetime
from typing import Dict, List, Any, Optional, TypeVar, Generic, Type
from pydantic import BaseModel, Field, ConfigDict

# 型変数
T = TypeVar('T')

class BaseModelConfig:
    """
    Pydanticモデルの共通設定。
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        validate_assignment=True,
        extra="ignore"
    )

class BaseEntity(BaseModel):
    """
    すべてのエンティティの基底クラス。
    """
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = BaseModelConfig.model_config

class BaseResponse(BaseModel):
    """
    すべてのレスポンスの基底クラス。
    """
    success: bool = True
    message: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class PaginatedResponse(BaseResponse, Generic[T]):
    """
    ページネーションされたレスポンスの基底クラス。
    """
    items: List[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 1
    
    model_config = BaseModelConfig.model_config

class ErrorResponse(BaseResponse):
    """
    エラーレスポンスの基底クラス。
    """
    success: bool = False
    error_code: str = "UNKNOWN_ERROR"
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = BaseModelConfig.model_config
```

### 2. ネットワークモデル (network.py)

ネットワーク関連のモデル定義を提供します。

```python
# common/models/network.py

from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

from .base import BaseEntity, BaseResponse, BaseModelConfig

class NodeData(BaseModel):
    """
    ノードデータモデル。
    """
    id: str
    label: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    size: Optional[float] = 5.0
    color: Optional[str] = "#1d4ed8"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class EdgeData(BaseModel):
    """
    エッジデータモデル。
    """
    source: str
    target: str
    width: Optional[float] = 1.0
    color: Optional[str] = "#94a3b8"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class GraphData(BaseModel):
    """
    グラフデータモデル。
    """
    nodes: List[NodeData] = Field(default_factory=list)
    edges: List[EdgeData] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    directed: bool = False
    
    model_config = BaseModelConfig.model_config

class NetworkBase(BaseEntity):
    """
    ネットワークの基底クラス。
    """
    name: str = "Untitled Network"
    conversation_id: Optional[int] = None
    graphml_content: str
    
    model_config = BaseModelConfig.model_config

class NetworkCreate(BaseModel):
    """
    ネットワーク作成モデル。
    """
    name: str = "Untitled Network"
    conversation_id: int
    graphml_content: str
    
    model_config = BaseModelConfig.model_config

class NetworkUpdate(BaseModel):
    """
    ネットワーク更新モデル。
    """
    name: Optional[str] = None
    graphml_content: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class Network(NetworkBase):
    """
    ネットワークモデル。
    """
    pass

class NetworkResponse(BaseResponse):
    """
    ネットワークレスポンスモデル。
    """
    network: Optional[Network] = None
    
    model_config = BaseModelConfig.model_config

class NetworkListResponse(BaseResponse):
    """
    ネットワークリストレスポンスモデル。
    """
    networks: List[Network] = Field(default_factory=list)
    
    model_config = BaseModelConfig.model_config

class LayoutRequest(BaseModel):
    """
    レイアウト計算リクエストモデル。
    """
    layout_type: str = "spring"
    layout_params: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class LayoutResponse(BaseResponse):
    """
    レイアウト計算レスポンスモデル。
    """
    layout_type: str
    positions: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class CentralityRequest(BaseModel):
    """
    中心性計算リクエストモデル。
    """
    centrality_type: str = "degree"
    centrality_params: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class CentralityResponse(BaseResponse):
    """
    中心性計算レスポンスモデル。
    """
    centrality_type: str
    centrality_values: Dict[str, float] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class GraphMLConvertRequest(BaseModel):
    """
    GraphML変換リクエストモデル。
    """
    graphml_content: str
    
    model_config = BaseModelConfig.model_config

class GraphMLConvertResponse(BaseResponse):
    """
    GraphML変換レスポンスモデル。
    """
    graphml_content: str
    
    model_config = BaseModelConfig.model_config

class VisualizationData(BaseModel):
    """
    ビジュアライゼーションデータモデル。
    """
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    
    model_config = BaseModelConfig.model_config

class CytoscapeData(BaseModel):
    """
    Cytoscape.js形式のデータモデル。
    """
    elements: Dict[str, List[Dict[str, Any]]] = Field(default_factory=lambda: {"nodes": [], "edges": []})
    
    model_config = BaseModelConfig.model_config
```

### 3. 会話モデル (conversation.py)

会話関連のモデル定義を提供します。

```python
# common/models/conversation.py

from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from .base import BaseEntity, BaseResponse, BaseModelConfig
from .network import Network

class ConversationBase(BaseEntity):
    """
    会話の基底クラス。
    """
    title: str = "New Conversation"
    user_id: Optional[int] = None
    
    model_config = BaseModelConfig.model_config

class ConversationCreate(BaseModel):
    """
    会話作成モデル。
    """
    title: str = "New Conversation"
    user_id: int
    
    model_config = BaseModelConfig.model_config

class ConversationUpdate(BaseModel):
    """
    会話更新モデル。
    """
    title: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class ChatMessageBase(BaseEntity):
    """
    チャットメッセージの基底クラス。
    """
    content: str
    role: str = "user"
    user_id: Optional[int] = None
    conversation_id: Optional[int] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class ChatMessageCreate(BaseModel):
    """
    チャットメッセージ作成モデル。
    """
    content: str
    role: str = "user"
    user_id: int
    conversation_id: int
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class ChatMessage(ChatMessageBase):
    """
    チャットメッセージモデル。
    """
    pass

class Conversation(ConversationBase):
    """
    会話モデル。
    """
    network: Optional[Network] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    
    model_config = BaseModelConfig.model_config

class ConversationResponse(BaseResponse):
    """
    会話レスポンスモデル。
    """
    conversation: Optional[Conversation] = None
    
    model_config = BaseModelConfig.model_config

class ConversationListResponse(BaseResponse):
    """
    会話リストレスポンスモデル。
    """
    conversations: List[Conversation] = Field(default_factory=list)
    
    model_config = BaseModelConfig.model_config

class ChatMessageResponse(BaseResponse):
    """
    チャットメッセージレスポンスモデル。
    """
    message: Optional[ChatMessage] = None
    
    model_config = BaseModelConfig.model_config

class ChatMessageListResponse(BaseResponse):
    """
    チャットメッセージリストレスポンスモデル。
    """
    messages: List[ChatMessage] = Field(default_factory=list)
    
    model_config = BaseModelConfig.model_config
```

### 4. ユーザーモデル (user.py)

ユーザー関連のモデル定義を提供します。

```python
# common/models/user.py

from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, EmailStr

from .base import BaseEntity, BaseResponse, BaseModelConfig

class UserBase(BaseEntity):
    """
    ユーザーの基底クラス。
    """
    username: str
    email: Optional[EmailStr] = None
    is_active: bool = True
    
    model_config = BaseModelConfig.model_config

class UserCreate(BaseModel):
    """
    ユーザー作成モデル。
    """
    username: str
    email: Optional[EmailStr] = None
    password: str
    
    model_config = BaseModelConfig.model_config

class UserUpdate(BaseModel):
    """
    ユーザー更新モデル。
    """
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    
    model_config = BaseModelConfig.model_config

class User(UserBase):
    """
    ユーザーモデル。
    """
    pass

class UserResponse(BaseResponse):
    """
    ユーザーレスポンスモデル。
    """
    user: Optional[User] = None
    
    model_config = BaseModelConfig.model_config

class UserListResponse(BaseResponse):
    """
    ユーザーリストレスポンスモデル。
    """
    users: List[User] = Field(default_factory=list)
    
    model_config = BaseModelConfig.model_config

class Token(BaseModel):
    """
    トークンモデル。
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    
    model_config = BaseModelConfig.model_config

class TokenData(BaseModel):
    """
    トークンデータモデル。
    """
    username: Optional[str] = None
    user_id: Optional[int] = None
    exp: Optional[datetime] = None
    
    model_config = BaseModelConfig.model_config

class LoginRequest(BaseModel):
    """
    ログインリクエストモデル。
    """
    username: str
    password: str
    
    model_config = BaseModelConfig.model_config

class LoginResponse(BaseResponse):
    """
    ログインレスポンスモデル。
    """
    token: Optional[Token] = None
    user: Optional[User] = None
    
    model_config = BaseModelConfig.model_config
```

### 5. GraphMLモデル (graphml.py)

GraphML関連のモデル定義を提供します。

```python
# common/models/graphml.py

from typing import Dict, List, Any, Optional, Union, Tuple
from pydantic import BaseModel, Field

from .base import BaseModelConfig

class AttributeData(BaseModel):
    """
    属性データモデル。
    """
    id: str
    name: str
    type: str = "string"
    for_element: str = "node"  # "node", "edge", "graph"
    default_value: Optional[Any] = None
    
    model_config = BaseModelConfig.model_config

class NodeData(BaseModel):
    """
    ノードデータモデル。
    """
    id: str
    label: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    size: Optional[float] = 5.0
    color: Optional[str] = "#1d4ed8"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class EdgeData(BaseModel):
    """
    エッジデータモデル。
    """
    source: str
    target: str
    width: Optional[float] = 1.0
    color: Optional[str] = "#94a3b8"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class GraphData(BaseModel):
    """
    グラフデータモデル。
    """
    nodes: List[NodeData] = Field(default_factory=list)
    edges: List[EdgeData] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    directed: bool = False
    
    model_config = BaseModelConfig.model_config

class GraphMLValidationError(BaseModel):
    """
    GraphML検証エラーモデル。
    """
    error: str
    description: Optional[str] = None
    location: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class GraphMLValidationWarning(BaseModel):
    """
    GraphML検証警告モデル。
    """
    warning: str
    description: Optional[str] = None
    location: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class GraphMLValidationResult(BaseModel):
    """
    GraphML検証結果モデル。
    """
    is_valid: bool = True
    errors: List[GraphMLValidationError] = Field(default_factory=list)
    warnings: List[GraphMLValidationWarning] = Field(default_factory=list)
    
    model_config = BaseModelConfig.model_config

class GraphMLConvertRequest(BaseModel):
    """
    GraphML変換リクエストモデル。
    """
    graphml_content: str
    calculate_centrality: bool = True
    fix_structure: bool = True
    validate: bool = True
    
    model_config = BaseModelConfig.model_config

class GraphMLConvertResponse(BaseModel):
    """
    GraphML変換レスポンスモデル。
    """
    success: bool = True
    graphml_content: Optional[str] = None
    validation_result: Optional[GraphMLValidationResult] = None
    error: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class LayoutData(BaseModel):
    """
    レイアウトデータモデル。
    """
    layout_type: str
    positions: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config

class CentralityData(BaseModel):
    """
    中心性データモデル。
    """
    centrality_type: str
    centrality_values: Dict[str, float] = Field(default_factory=dict)
    
    model_config = BaseModelConfig.model_config
```

### 6. 型定義 (types.py)

共通の型定義を提供します。

```python
# common/models/types.py

from typing import Dict, List, Any, Optional, Union, TypeVar, Generic, Type
from enum import Enum, auto

# 型変数
T = TypeVar('T')

class Role(str, Enum):
    """
    ユーザーロール。
    """
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"

class MessageRole(str, Enum):
    """
    メッセージロール。
    """
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class LayoutType(str, Enum):
    """
    レイアウトタイプ。
    """
    SPRING = "spring"
    CIRCULAR = "circular"
    RANDOM = "random"
    SPECTRAL = "spectral"
    SHELL = "shell"
    KAMADA_KAWAI = "kamada_kawai"
    FRUCHTERMAN_REINGOLD = "fruchterman_reingold"
    SPIRAL = "spiral"
    MULTIPARTITE = "multipartite"
    BIPARTITE = "bipartite"

class CentralityType(str, Enum):
    """
    中心性タイプ。
    """
    DEGREE = "degree"
    CLOSENESS = "closeness"
    BETWEENNESS = "betweenness"
    EIGENVECTOR = "eigenvector"
    PAGERANK = "pagerank"
    KATZ = "katz"
    LOAD = "load"
    HARMONIC = "harmonic"
    SUBGRAPH = "subgraph"
    COMMUNICABILITY_BETWEENNESS = "communicability_betweenness"

class ErrorCode(str, Enum):
    """
    エラーコード。
    """
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    GRAPHML_VALIDATION_ERROR = "GRAPHML_VALIDATION_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    GRAPH_PROCESSING_ERROR = "GRAPH_PROCESSING_ERROR"
    LAYOUT_PROCESSING_ERROR = "LAYOUT_PROCESSING_ERROR"
    CENTRALITY_PROCESSING_ERROR = "CENTRALITY_PROCESSING_ERROR"
    COMMUNICATION_ERROR = "COMMUNICATION_ERROR"
    MCP_COMMUNICATION_ERROR = "MCP_COMMUNICATION_ERROR"
    DATABASE_COMMUNICATION_ERROR = "DATABASE_COMMUNICATION_ERROR"
    LLM_COMMUNICATION_ERROR = "LLM_COMMUNICATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_CREDENTIALS_ERROR = "INVALID_CREDENTIALS_ERROR"
    TOKEN_EXPIRED_ERROR = "TOKEN_EXPIRED_ERROR"
    PERMISSION_DENIED_ERROR = "PERMISSION_DENIED_ERROR"
    RESOURCE_ERROR = "RESOURCE_ERROR"
    RESOURCE_NOT_FOUND_ERROR = "RESOURCE_NOT_FOUND_ERROR"
    RESOURCE_CONFLICT_ERROR = "RESOURCE_CONFLICT_ERROR"
    RESOURCE_LIMIT_EXCEEDED_ERROR = "RESOURCE_LIMIT_EXCEEDED_ERROR"
```

## SQLAlchemyモデルとの統合

Pydanticモデルとして定義した共通モデルをSQLAlchemyモデルと統合するためのヘルパー関数を提供します。

```python
# common/models/__init__.py

from typing import Dict, List, Any, Optional, TypeVar, Generic, Type, Union
from pydantic import BaseModel

# 型変数
T = TypeVar('T')
ModelType = TypeVar('ModelType')
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)

def model_to_schema(model: Any, schema_cls: Type[T]) -> T:
    """
    SQLAlchemyモデルをPydanticスキーマに変換する。
    
    Args:
        model: SQLAlchemyモデル
        schema_cls: Pydanticスキーマクラス
        
    Returns:
        Pydanticスキーマインスタンス
    """
    return schema_cls.model_validate(model)

def schema_to_model(schema: BaseModel, model_cls: Type[ModelType]) -> ModelType:
    """
    PydanticスキーマをSQLAlchemyモデルに変換する。
    
    Args:
        schema: Pydanticスキーマ
        model_cls: SQLAlchemyモデルクラス
        
    Returns:
        SQLAlchemyモデルインスタンス
    """
    model_data = schema.model_dump(exclude_unset=True)
    return model_cls(**model_data)

def update_model_from_schema(model: ModelType, schema: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
    """
    PydanticスキーマからSQLAlchemyモデルを更新する。
    
    Args:
        model: 更新するSQLAlchemyモデル
        schema: 更新データを含むPydanticスキーマまたは辞書
        
    Returns:
        更新されたSQLAlchemyモデル
    """
    update_data = schema.model_dump(exclude_unset=True) if isinstance(schema, BaseModel) else schema
    for key, value in update_data.items():
        setattr(model, key, value)
    return model
```

## 使用例

### 1. API側での使用例

```python
# API/routers/network.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models as db_models
from common.models.network import Network, NetworkCreate, NetworkResponse, NetworkListResponse
from common.models import model_to_schema

router = APIRouter()

@router.get("/{network_id}", response_model=NetworkResponse)
def get_network(network_id: int, db: Session = Depends(get_db)):
    db_network = db.query(db_models.Network).filter(db_models.Network.id == network_id).first()
    if not db_network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # SQLAlchemyモデルをPydanticスキーマに変換
    network = model_to_schema(db_network, Network)
    
    return NetworkResponse(
        success=True,
        network=network
    )

@router.get("/", response_model=NetworkListResponse)
def get_networks(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    db_networks = db.query(db_models.Network).offset(skip).limit(limit).all()
    
    # SQLAlchemyモデルのリストをPydanticスキーマのリストに変換
    networks = [model_to_schema(db_network, Network) for db_network in db_networks]
    
    return NetworkListResponse(
        success=True,
        networks=networks
    )
```

### 2. NetworkXMCP側での使用例

```python
# NetworkXMCP/tools/layout.py

from typing import Dict, Any
from common.models.network import LayoutRequest, LayoutResponse
from common.models.graphml import GraphData
from common.utils.graphml.parser import parse_graphml_to_data

def calculate_layout(graphml_content: str, layout_request: LayoutRequest) -> LayoutResponse:
    """
    レイアウトを計算する。
    
    Args:
        graphml_content: GraphML形式の文字列
        layout_request: レイアウト計算リクエスト
        
    Returns:
        LayoutResponse: レイアウト計算レスポンス
    """
    # GraphMLをパース
    graph_data = parse_graphml_to_data(graphml_content)
    
    # レイアウトを計算
    # ...
    
    # 結果を返す
    return LayoutResponse(
        success=True,
        layout_type=layout_request.layout_type,
        positions=positions
    )
```

## データベースモデルとの関係

共通モデル定義はPydanticを使用したスキーマ定義であり、データベースモデルはSQLAlchemyを使用して別途定義します。両者の関係は以下のようになります：

1. **データベースモデル**: データの永続化を担当
2. **共通モデル**: APIリクエスト/レスポンスの検証と変換を担当

これにより、データベーススキーマの変更がAPIに与える影響を最小限に抑えることができます。

## まとめ

共通データモデル定義を設計することで、以下のメリットが得られます：

1. コードの重複を削減
2. モデル定義の一貫性を確保
3. 機能拡張を容易にする
4. 依存関係を明確にする
5. 型安全性を向上させる

この設計を実装することで、LLMGraphvisプロジェクト全体でデータモデルが統一され、開発効率が向上します。