# API側ネットワーク機能モジュール分割設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトのAPI側ネットワーク機能モジュールの分割設計について説明します。現在、`API/routers/network.py`ファイルは390行と大きく、複数の責務が混在しています。このファイルを機能別のサブモジュールに分割することで、コードの可読性、保守性、拡張性を向上させることを目的としています。

## 現状の課題

1. **ファイルサイズの肥大化**: `network.py`が390行と大きく、全体を把握しにくい
2. **責務の混在**: アップロード、エクスポート、ビジュアライゼーション、レイアウト処理など複数の責務が混在している
3. **コードの重複**: 類似の処理が複数箇所に存在する
4. **テストの困難さ**: 大きなファイルはテストが困難

## 設計目標

1. **単一責任の原則**: 各モジュールが単一の責務を持つようにする
2. **コードの再利用**: 共通処理を抽出し、再利用可能にする
3. **テスト容易性**: 各モジュールを独立してテストできるようにする
4. **拡張性**: 新しい機能を容易に追加できるようにする
5. **API互換性**: 既存のAPIエンドポイントとの互換性を維持する

## モジュール構造

```
API/
  routers/
    network/
      __init__.py        # ルーターの初期化と集約
      upload.py          # ネットワークアップロード機能
      export.py          # ネットワークエクスポート機能
      visualization.py   # ビジュアライゼーション機能
      layout.py          # レイアウト処理機能
      utils.py           # ユーティリティ関数
```

## 各モジュールの責務

### 1. `__init__.py`

ルーターの初期化と各サブモジュールのルーターの集約を担当します。

```python
# API/routers/network/__init__.py

from fastapi import APIRouter
from . import upload, export, visualization, layout

# メインルーターの作成
router = APIRouter(
    prefix="/network",
    tags=["network"],
    responses={404: {"description": "Not found"}},
)

# サブモジュールのルーターをインクルード
router.include_router(upload.router)
router.include_router(export.router)
router.include_router(visualization.router)
router.include_router(layout.router)

# 共通のユーティリティ関数をエクスポート
from .utils import get_network_for_user
```

### 2. `utils.py`

共通のユーティリティ関数を提供します。

```python
# API/routers/network/utils.py

from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

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

### 3. `upload.py`

ネットワークのアップロード機能を提供します。

```python
# API/routers/network/upload.py

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging

import models
import schemas
import auth
from database import get_db
from services import mcp_client
from services.graphml import validate_graphml, convert_graphml
from common.exceptions import GraphMLValidationError, GraphProcessingError, MCPCommunicationError
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
        
        # GraphMLの検証
        validate_graphml(graphml_content_str)

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
            # ネットワークは正常に作成されたので、例外は発生させない

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

@router.post("/{conversation_id}/upload", response_model=schemas.Network)
async def upload_and_overwrite_network(
    conversation_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    既存のネットワークを上書きするためにGraphMLファイルをアップロードします。
    
    Args:
        conversation_id: ネットワークを含む会話のID
        file: アップロードするGraphMLファイル
        current_user: 現在の認証済みユーザー
        db: データベースセッション
        
    Returns:
        更新されたネットワーク
    """
    if not file.filename.endswith(".graphml"):
        raise GraphMLValidationError(
            message="Invalid file type. Please upload a .graphml file.",
            validation_errors=[{"error": "Invalid file extension"}]
        )
    
    # 会話を検索し、所有権を確認
    db_conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()

    if not db_conversation:
        raise ResourceNotFoundError(
            resource_type="Conversation",
            resource_id=str(conversation_id),
            message="Conversation not found"
        )

    db_network = db_conversation.network
    if not db_network:
        raise ResourceNotFoundError(
            resource_type="Network",
            resource_id=f"for conversation {conversation_id}",
            message="Network not found for this conversation"
        )

    try:
        # ファイルの読み込み
        graphml_content_bytes = await file.read()
        graphml_content_str = graphml_content_bytes.decode("utf-8")
        
        # GraphMLの検証
        validate_graphml(graphml_content_str)

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

        # ネットワークコンテンツの更新
        db_network.graphml_content = normalized_graphml_str
        db_network.name = file.filename
        db.commit()
        db.refresh(db_network)
        
        # ネットワークのデフォルトレイアウト（spring）を計算
        try:
            await mcp_client.change_layout(db_network.id, "spring")
            logger.info(f"Applied default spring layout to network {db_network.id}")
        except mcp_client.MCPError as e:
            # エラーをログに記録するが、アップロードは失敗させない
            logger.error(f"Error applying default layout: {e.message}")
            # ネットワークは正常に更新されたので、例外は発生させない
        
        return db_network
    
    except (GraphMLValidationError, MCPCommunicationError, ResourceNotFoundError) as e:
        # 既知の例外は再送
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in upload_and_overwrite_network: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"An unexpected error occurred: {str(e)}",
            context={"file_name": file.filename, "conversation_id": conversation_id}
        )
```

### 4. `export.py`

ネットワークのエクスポート機能を提供します。

```python
# API/routers/network/export.py

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

import models
import auth
from database import get_db
from .utils import get_network_for_user
from common.logging.config import get_logger

logger = get_logger("api.routers.network.export")

router = APIRouter()

@router.get("/{network_id}/export")
async def export_network_graphml(
    network_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    ネットワークをGraphMLファイルとしてエクスポートします。
    
    Args:
        network_id: エクスポートするネットワークのID
        current_user: 現在の認証済みユーザー
        db: データベースセッション
        
    Returns:
        GraphMLファイルをレスポンスとして返す
    """
    logger.info(f"Exporting network {network_id} as GraphML")
    
    # ユーザーのネットワークを取得
    db_network = get_network_for_user(db, network_id, current_user.id)
    
    return Response(
        content=db_network.graphml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=network_{network_id}.graphml"}
    )
```

### 5. `visualization.py`

ネットワークのビジュアライゼーション機能を提供します。

```python
# API/routers/network/visualization.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import networkx as nx
import io
import json

import models
import auth
from database import get_db
from .utils import get_network_for_user
from services.visualization import create_cytoscape_data, create_visualization_data
from common.exceptions import GraphProcessingError
from common.logging.config import get_logger

logger = get_logger("api.routers.network.visualization")

router = APIRouter()

@router.get("/{network_id}/cytoscape", response_model=Dict[str, Any])
async def get_network_cytoscape_format(
    network_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ネットワークをCytoscape.js JSON形式で取得します。
    
    Args:
        network_id: 取得するネットワークのID
        current_user: 現在の認証済みユーザー
        db: データベースセッション
        
    Returns:
        Cytoscape.js形式のネットワークデータを含む辞書
    """
    logger.info(f"Getting network {network_id} in Cytoscape.js format")
    
    # ユーザーのネットワークを取得
    db_network = get_network_for_user(db, network_id, current_user.id)
    
    try:
        # ビジュアライゼーションサービスを使用してCytoscapeデータを作成
        cytoscape_data = create_cytoscape_data(db_network.graphml_content)
        return cytoscape_data
    except Exception as e:
        logger.error(f"Error processing GraphML for Cytoscape: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"Error processing GraphML: {str(e)}",
            context={"network_id": network_id}
        )

@router.get("/{network_id}/visdata", response_model=Dict[str, Any])
async def get_network_visualization_data(
    network_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ビジュアライゼーション用に最適化されたネットワークデータを取得します。
    
    このエンドポイントは、ネットワーク構造と視覚的なマッピングルールを組み合わせて
    レンダリングデータを動的に生成します。
    
    Args:
        network_id: 取得するネットワークのID
        current_user: 現在の認証済みユーザー
        db: データベースセッション
        
    Returns:
        ビジュアライゼーション用のノードとリンクデータを含む辞書
    """
    logger.info(f"Getting visualization data for network {network_id}")
    
    # ユーザーのネットワークを取得
    db_network = get_network_for_user(db, network_id, current_user.id)
    
    try:
        # ビジュアライゼーションサービスを使用してビジュアライゼーションデータを作成
        vis_data = create_visualization_data(db_network.graphml_content)
        return vis_data
    except Exception as e:
        logger.error(f"Error generating visualization data: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"Error generating visualization data: {str(e)}",
            context={"network_id": network_id}
        )
```

### 6. `layout.py`

ネットワークのレイアウト処理機能を提供します。

```python
# API/routers/network/layout.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

import models
import auth
from database import get_db
from .utils import get_network_for_user
from services import mcp_client
from common.exceptions import MCPCommunicationError, GraphProcessingError
from common.logging.config import get_logger

logger = get_logger("api.routers.network.layout")

router = APIRouter()

@router.post("/{network_id}/layout")
async def calculate_network_layout(
    network_id: int,
    layout_type: str = "spring",
    layout_params: Dict[str, Any] = {},
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ネットワークのレイアウトを計算します。
    
    このエンドポイントは、レイアウト計算をNetworkXMCPサービスにプロキシします。
    
    Args:
        network_id: ネットワークのID
        layout_type: 適用するレイアウトのタイプ
        layout_params: レイアウトアルゴリズムのパラメータ
        current_user: 現在の認証済みユーザー
        db: データベースセッション
        
    Returns:
        NetworkXMCPサービスからのレイアウト計算結果
    """
    logger.info(f"Calculating {layout_type} layout for network {network_id}")
    
    # ユーザーがこのネットワークにアクセスできるか確認
    get_network_for_user(db, network_id, current_user.id)
    
    try:
        # NetworkXMCPサービスを呼び出してレイアウトを計算
        result = await mcp_client.change_layout(network_id, layout_type, layout_params)
        return result
    except mcp_client.MCPError as e:
        logger.error(f"Error from NetworkXMCP: {e.message}")
        raise MCPCommunicationError(
            message=e.message,
            service_name="NetworkXMCP",
            status_code=e.status_code,
            context={"network_id": network_id, "layout_type": layout_type}
        )
    except Exception as e:
        logger.error(f"Unexpected error in calculate_network_layout: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"An unexpected error occurred: {str(e)}",
            context={"network_id": network_id, "layout_type": layout_type}
        )
```

## 新しいサービスモジュール

ネットワーク機能の分割に伴い、以下の新しいサービスモジュールを作成します。

### 1. GraphML処理サービス

```python
# API/services/graphml/__init__.py

from .validator import validate_graphml
from .converter import convert_graphml
```

```python
# API/services/graphml/validator.py

from typing import List, Dict, Any
from common.exceptions import GraphMLValidationError
from common.utils.graphml.validator import validate_graphml_content
from common.logging.config import get_logger

logger = get_logger("api.services.graphml.validator")

def validate_graphml(graphml_content: str) -> bool:
    """
    GraphML文字列を検証します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        bool: 検証に成功した場合はTrue
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
    """
    try:
        return validate_graphml_content(graphml_content)
    except GraphMLValidationError as e:
        # 共通モジュールからの例外をそのまま再送
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in validate_graphml: {str(e)}", exc_info=True)
        raise GraphMLValidationError(
            message=f"Failed to validate GraphML: {str(e)}",
            validation_errors=[{"error": str(e)}],
            context={"content_length": len(graphml_content)}
        )
```

```python
# API/services/graphml/converter.py

from typing import Dict, Any
from common.exceptions import GraphProcessingError
from common.utils.graphml.converter import convert_to_standard_graphml
from common.logging.config import get_logger

logger = get_logger("api.services.graphml.converter")

def convert_graphml(graphml_content: str) -> str:
    """
    GraphML文字列を標準形式に変換します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        str: 標準形式のGraphML文字列
        
    Raises:
        GraphProcessingError: GraphMLの変換に失敗した場合
    """
    try:
        return convert_to_standard_graphml(graphml_content)
    except Exception as e:
        logger.error(f"Error converting GraphML: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"Failed to convert GraphML: {str(e)}",
            context={"content_length": len(graphml_content)}
        )
```

### 2. ビジュアライゼーションサービス

```python
# API/services/visualization/__init__.py

from .cytoscape import create_cytoscape_data
from .visdata import create_visualization_data
```

```python
# API/services/visualization/cytoscape.py

from typing import Dict, List, Any
import networkx as nx
import io
from common.exceptions import GraphProcessingError
from common.logging.config import get_logger

logger = get_logger("api.services.visualization.cytoscape")

def create_cytoscape_data(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列からCytoscape.js形式のデータを作成します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: Cytoscape.js形式のデータ
        
    Raises:
        GraphProcessingError: データ作成に失敗した場合
    """
    try:
        # GraphMLをNetworkXグラフに変換
        content_io = io.StringIO(graphml_content)
        G = nx.read_graphml(content_io)
        
        # 位置情報もCytoscape形式に含める
        nodes = []
        for n, data in G.nodes(data=True):
            node_data = {"data": {"id": str(n), **data}}
            if 'x' in data and 'y' in data:
                node_data["position"] = {"x": data['x'], "y": data['y']}
            nodes.append(node_data)
            
        edges = [{"data": {"source": str(u), "target": str(v), **d}} for u, v, d in G.edges(data=True)]
        
        return {"elements": {"nodes": nodes, "edges": edges}}
    except Exception as e:
        logger.error(f"Error creating Cytoscape data: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"Error creating Cytoscape data: {str(e)}",
            context={"content_length": len(graphml_content)}
        )
```

```python
# API/services/visualization/visdata.py

from typing import Dict, List, Any
import networkx as nx
import io
from common.exceptions import GraphProcessingError
from common.logging.config import get_logger

logger = get_logger("api.services.visualization.visdata")

def create_visualization_data(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列からビジュアライゼーション用のデータを作成します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: ビジュアライゼーション用のデータ
        
    Raises:
        GraphProcessingError: データ作成に失敗した場合
    """
    try:
        # GraphMLをNetworkXグラフに変換
        content_io = io.StringIO(graphml_content)
        G = nx.read_graphml(content_io)
        
        # デフォルトの視覚的プロパティ
        default_node_size = 5
        default_node_color = "#82b3ff"  # システムのテーマカラーに合わせた明るい青
        default_edge_width = 1
        default_edge_color = "#cccccc"  # 他の要素を邪魔しない薄いグレー
        
        # ノードデータの準備
        nodes_data = []
        for node_id, attrs in G.nodes(data=True):
            # 位置情報の抽出
            x = float(attrs.get('x', 0))
            y = float(attrs.get('y', 0))
            
            # 視覚的プロパティの抽出またはデフォルト設定
            size = float(attrs.get('size', default_node_size))
            color = attrs.get('color', default_node_color)
            label = attrs.get('name', str(node_id))
            
            # ノードオブジェクトの作成
            node = {
                "id": str(node_id),
                "label": label,
                "x": x,
                "y": y,
                "size": size,
                "color": color
            }
            
            # 追加の属性を追加
            for key, value in attrs.items():
                if key not in ["id", "label", "x", "y", "size", "color", "name"]:
                    node[key] = value
            
            nodes_data.append(node)
        
        # エッジデータの準備
        links_data = []
        for source, target, attrs in G.edges(data=True):
            # 視覚的プロパティの抽出またはデフォルト設定
            width = float(attrs.get('width', default_edge_width))
            color = attrs.get('color', default_edge_color)
            
            # エッジオブジェクトの作成
            edge = {
                "source": str(source),
                "target": str(target),
                "width": width,
                "color": color
            }
            
            # 追加の属性を追加
            for key, value in attrs.items():
                if key not in ["source", "target", "width", "color"]:
                    edge[key] = value
            
            links_data.append(edge)
        
        # ビジュアライゼーションデータを返す
        return {
            "nodes": nodes_data,
            "links": links_data
        }
    except Exception as e:
        logger.error(f"Error creating visualization data: {str(e)}", exc_info=True)
        raise GraphProcessingError(
            message=f"Error creating visualization data: {str(e)}",
            context={"content_length": len(graphml_content)}
        )
```

## 移行計画

1. **新しいディレクトリ構造の作成**:
   - `API/routers/network/` ディレクトリを作成
   - 各サブモジュ