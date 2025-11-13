# API側データモデルとスキーマの整理設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトのAPI側データモデルとスキーマの整理設計について説明します。現在、`API/models.py`と`API/schemas.py`ファイルには複数のモデル定義が混在しています。これらのファイルを機能別のモジュールに分割することで、コードの可読性、保守性、拡張性を向上させることを目的としています。

## 現状の課題

1. **モデル定義の混在**: ユーザー、会話、ネットワーク、チャットメッセージなど複数のモデル定義が単一ファイルに混在している
2. **ファイルサイズの肥大化**: 将来的な機能追加によりファイルサイズが肥大化する可能性がある
3. **依存関係の複雑さ**: モデル間の依存関係が不明確
4. **テストの困難さ**: 大きなファイルはテストが困難

## 設計目標

1. **単一責任の原則**: 各モジュールが単一の責務を持つようにする
2. **コードの再利用**: 共通処理を抽出し、再利用可能にする
3. **テスト容易性**: 各モジュールを独立してテストできるようにする
4. **拡張性**: 新しいモデルを容易に追加できるようにする
5. **依存関係の明確化**: モデル間の依存関係を明確にする

## モジュール構造

### データベースモデル (models)

```
API/
  models/
    __init__.py        # モデルのエクスポート
    base.py            # 基本モデル定義
    user.py            # ユーザー関連モデル
    conversation.py    # 会話関連モデル
    network.py         # ネットワーク関連モデル
    chat.py            # チャット関連モデル
```

### APIスキーマ (schemas)

```
API/
  schemas/
    __init__.py        # スキーマのエクスポート
    base.py            # 基本スキーマ定義
    user.py            # ユーザー関連スキーマ
    conversation.py    # 会話関連スキーマ
    network.py         # ネットワーク関連スキーマ
    chat.py            # チャット関連スキーマ
```

## 各モジュールの責務

### 1. データベースモデル (models)

#### 1.1 `models/__init__.py`

モデルのエクスポートを担当します。

```python
# API/models/__init__.py

from .base import Base
from .user import User
from .conversation import Conversation
from .network import Network
from .chat import ChatMessage

__all__ = [
    "Base",
    "User",
    "Conversation",
    "Network",
    "ChatMessage"
]
```

#### 1.2 `models/base.py`

基本モデル定義を提供します。

```python
# API/models/base.py

from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from database import Base

class BaseModel:
    """
    すべてのモデルの基底クラス。
    """
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

#### 1.3 `models/user.py`

ユーザー関連モデルを提供します。

```python
# API/models/user.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import BaseModel
from database import Base

class User(Base, BaseModel):
    """
    ユーザーモデル。
    """
    __tablename__ = "users"

    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
```

#### 1.4 `models/conversation.py`

会話関連モデルを提供します。

```python
# API/models/conversation.py

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import BaseModel
from database import Base

class Conversation(Base, BaseModel):
    """
    会話モデル。
    """
    __tablename__ = "conversations"
    
    title = Column(String, default="New Conversation")
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")
    network = relationship("Network", back_populates="conversation", uselist=False, cascade="all, delete-orphan")
```

#### 1.5 `models/network.py`

ネットワーク関連モデルを提供します。

```python
# API/models/network.py

from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import BaseModel
from database import Base

class Network(Base, BaseModel):
    """
    ネットワークモデル。
    """
    __tablename__ = "networks"
    
    name = Column(String, default="Untitled Network")
    conversation_id = Column(Integer, ForeignKey("conversations.id"), unique=True)
    graphml_content = Column(Text, nullable=False) # GraphML content
    
    # Relationships
    conversation = relationship("Conversation", back_populates="network")
```

#### 1.6 `models/chat.py`

チャット関連モデルを提供します。

```python
# API/models/chat.py

from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import BaseModel
from database import Base

class ChatMessage(Base, BaseModel):
    """
    チャットメッセージモデル。
    """
    __tablename__ = "chat_messages"
    
    content = Column(Text)
    role = Column(String)  # "user" or "assistant"
    user_id = Column(Integer, ForeignKey("users.id"))
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    meta_data = Column(Text, default="{}")  # JSON string for additional metadata
    
    # Relationships
    user = relationship("User", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")
```

### 2. APIスキーマ (schemas)

#### 2.1 `schemas/__init__.py`

スキーマのエクスポートを担当します。

```python
# API/schemas/__init__.py

from .base import BaseResponse, PaginatedResponse, ErrorResponse
from .user import User, UserCreate, UserUpdate, Token, TokenData
from .conversation import Conversation, ConversationCreate, ConversationUpdate
from .network import Network, NetworkCreate, NetworkUpdate
from .chat import ChatMessage, ChatMessageCreate

__all__ = [
    "BaseResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "User",
    "UserCreate",
    "UserUpdate",
    "Token",
    "TokenData",
    "Conversation",
    "ConversationCreate",
    "ConversationUpdate",
    "Network",
    "NetworkCreate",
    "NetworkUpdate",
    "ChatMessage",
    "ChatMessageCreate"
]
```

#### 2.2 `schemas/base.py`

基本スキーマ定義を提供します。

```python
# API/schemas/base.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Generic, TypeVar
from datetime import datetime

# 型変数
T = TypeVar('T')

class BaseModelConfig:
    """
    Pydanticモデルの共通設定。
    """
    model_config = {
        "from_attributes": True
    }

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

#### 2.3 `schemas/user.py`

ユーザー関連スキーマを提供します。

```python
# API/schemas/user.py

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base import BaseModelConfig

class UserBase(BaseModel):
    """
    ユーザーの基底クラス。
    """
    username: str
    
    model_config = BaseModelConfig.model_config

class UserCreate(UserBase):
    """
    ユーザー作成モデル。
    """
    password: str
    
    model_config = BaseModelConfig.model_config

class UserUpdate(BaseModel):
    """
    ユーザー更新モデル。
    """
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    
    model_config = BaseModelConfig.model_config

class User(UserBase):
    """
    ユーザーモデル。
    """
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = BaseModelConfig.model_config

class Token(BaseModel):
    """
    トークンモデル。
    """
    access_token: str
    token_type: str
    
    model_config = BaseModelConfig.model_config

class TokenData(BaseModel):
    """
    トークンデータモデル。
    """
    username: Optional[str] = None
    
    model_config = BaseModelConfig.model_config
```

#### 2.4 `schemas/conversation.py`

会話関連スキーマを提供します。

```python
# API/schemas/conversation.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base import BaseModelConfig
from .network import Network

class ConversationBase(BaseModel):
    """
    会話の基底クラス。
    """
    title: str = "New Conversation"
    
    model_config = BaseModelConfig.model_config

class ConversationCreate(ConversationBase):
    """
    会話作成モデル。
    """
    pass
    
    model_config = BaseModelConfig.model_config

class ConversationUpdate(BaseModel):
    """
    会話更新モデル。
    """
    title: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class Conversation(ConversationBase):
    """
    会話モデル。
    """
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    network: Optional[Network] = None
    
    model_config = BaseModelConfig.model_config
```

#### 2.5 `schemas/network.py`

ネットワーク関連スキーマを提供します。

```python
# API/schemas/network.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base import BaseModelConfig

class NetworkBase(BaseModel):
    """
    ネットワークの基底クラス。
    """
    name: str = "Untitled Network"
    graphml_content: str
    
    model_config = BaseModelConfig.model_config

class NetworkCreate(NetworkBase):
    """
    ネットワーク作成モデル。
    """
    pass
    
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
    id: int
    conversation_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = BaseModelConfig.model_config
```

#### 2.6 `schemas/chat.py`

チャット関連スキーマを提供します。

```python
# API/schemas/chat.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from .base import BaseModelConfig

class ChatMessageBase(BaseModel):
    """
    チャットメッセージの基底クラス。
    """
    content: str
    role: str = "user"
    
    model_config = BaseModelConfig.model_config

class ChatMessageCreate(ChatMessageBase):
    """
    チャットメッセージ作成モデル。
    """
    model: Optional[str] = None
    
    model_config = BaseModelConfig.model_config

class ChatMessage(ChatMessageBase):
    """
    チャットメッセージモデル。
    """
    id: int
    user_id: int
    conversation_id: int
    meta_data: Optional[str] = "{}"
    created_at: datetime
    
    model_config = BaseModelConfig.model_config

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as a dictionary."""
        try:
            return json.loads(self.meta_data)
        except (json.JSONDecodeError, TypeError):
            return {}
```

## 移行計画

1. **新しいディレクトリ構造の作成**:
   - `API/models/` ディレクトリを作成
   - `API/schemas/` ディレクトリを作成
   - 各サブモジュールファイルを作成

2. **既存のモデル定義の移行**:
   - `models.py` から各モデルを対応するサブモジュールに移動
   - 依存関係を修正

3. **既存のスキーマ定義の移行**:
   - `schemas.py` から各スキーマを対応するサブモジュールに移動
   - 依存関係を修正

4. **インポート文の更新**:
   - 他のモジュールからのインポート文を更新
   - 例: `import models` → `from models import User, Conversation, Network, ChatMessage`

5. **テストの更新**:
   - テストコードのインポート文を更新
   - 必要に応じてテストを追加

## 注意点

1. **循環インポートの回避**:
   - 循環インポートが発生しないように注意する
   - 必要に応じて型ヒントを文字列で指定する

2. **後方互換性の維持**:
   - 既存のコードが動作するように後方互換性を維持する
   - `__init__.py` で適切にエクスポートする

3. **共通モデルとの統合**:
   - 共通モデル定義と統合する方法を検討する
   - 将来的には共通モデルに移行することを考慮する

## 期待される効果

1. **コードの可読性向上**: 各モデルが独立したファイルに配置されるため、コードの可読性が向上する
2. **保守性の向上**: 各モデルを独立して修正できるため、保守性が向上する
3. **拡張性の向上**: 新しいモデルを追加する際に既存のコードを変更する必要がなくなる
4. **テスト容易性の向上**: 各モデルを独立してテストできるため、テストが容易になる
5. **依存関係の明確化**: モデル間の依存関係が明確になる