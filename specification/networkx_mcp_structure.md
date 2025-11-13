# NetworkXMCPモジュール構造改善設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトのNetworkXMCPサービスのモジュール構造改善設計について説明します。現在、`NetworkXMCP/main.py`ファイルはデータベース関連コードを含み、`tools/network_tools.py`ファイルは915行と非常に大きく、複数の責務が混在しています。これらのファイルを機能別のモジュールに分割することで、コードの可読性、保守性、拡張性を向上させることを目的としています。

## 現状の課題

1. **main.pyの責務混在**: データベース関連コードとAPIエンドポイントが混在している
2. **network_tools.pyの肥大化**: 915行と非常に大きく、複数の責務が混在している
3. **GraphML処理の重複**: GraphML処理コードがAPI側と重複している
4. **キャッシュ管理の複雑さ**: キャッシュ管理コードがAPIエンドポイント内に直接記述されている

## 設計目標

1. **単一責任の原則**: 各モジュールが単一の責務を持つようにする
2. **コードの再利用**: 共通処理を抽出し、再利用可能にする
3. **テスト容易性**: 各モジュールを独立してテストできるようにする
4. **拡張性**: 新しい機能を容易に追加できるようにする
5. **API互換性**: 既存のAPIエンドポイントとの互換性を維持する

## モジュール構造

```
NetworkXMCP/
  database/
    __init__.py        # データベース初期化
    models.py          # SQLAlchemyモデル定義
    session.py         # セッション管理
    operations.py      # データベース操作
  
  graphml/
    __init__.py        # モジュール初期化
    converter.py       # GraphML変換機能
    validator.py       # GraphML検証機能
    fixer.py           # GraphML修正機能
  
  tools/
    __init__.py        # モジュール初期化
    creation.py        # ネットワーク作成機能
    parsing.py         # ネットワークパース機能
    export.py          # ネットワークエクスポート機能
    analysis.py        # ネットワーク分析機能
  
  cache/
    __init__.py        # モジュール初期化
    manager.py         # キャッシュ管理
    strategies.py      # キャッシュ戦略
    invalidation.py    # キャッシュ無効化
  
  core/
    __init__.py        # モジュール初期化
    config.py          # 設定管理
    errors.py          # エラーハンドリング
  
  api/
    __init__.py        # モジュール初期化
    layout.py          # レイアウトAPI
    centrality.py      # 中心性API
    graphml.py         # GraphML API
  
  main.py              # アプリケーションエントリーポイント
```

## 主要コンポーネント

### 1. データベース関連コード分離

#### 1.1 `database/models.py`

SQLAlchemyモデル定義を提供します。

```python
# NetworkXMCP/database/models.py

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Conversation(Base):
    """
    会話モデル。
    """
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)

class Network(Base):
    """
    ネットワークモデル。
    """
    __tablename__ = "networks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Untitled Network")
    conversation_id = Column(Integer, ForeignKey("conversations.id"), unique=True)
    graphml_content = Column(Text, nullable=False)
    layout_cache = Column(Text, default="{}")
    centrality_cache = Column(Text, default="{}")

    conversation = relationship("Conversation")
```

#### 1.2 `database/session.py`

データベースセッション管理を提供します。

```python
# NetworkXMCP/database/session.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from common.logging.config import get_logger

logger = get_logger("networkx_mcp.database.session")

# データベースURL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@db:5432/graphvis")

# エンジンの作成
engine = create_engine(DATABASE_URL)

# セッションの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 依存性注入用のセッション取得関数
def get_db():
    """
    依存性注入用のデータベースセッションを提供します。
    
    Yields:
        新しいデータベースセッション
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    データベースを初期化します。
    """
    from .models import Base
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        raise
```

#### 1.3 `database/operations.py`

データベース操作を提供します。

```python
# NetworkXMCP/database/operations.py

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import json

from .models import Network
from common.exceptions import ResourceNotFoundError, DatabaseCommunicationError
from common.logging.config import get_logger

logger = get_logger("networkx_mcp.database.operations")

def get_network(db: Session, network_id: int) -> Network:
    """
    指定されたIDのネットワークを取得します。
    
    Args:
        db: データベースセッション
        network_id: ネットワークID
        
    Returns:
        ネットワークオブジェクト
        
    Raises:
        ResourceNotFoundError: ネットワークが見つからない場合
    """
    try:
        network = db.query(Network).filter(Network.id == network_id).first()
        if not network:
            logger.warning(f"Network {network_id} not found")
            raise ResourceNotFoundError(
                resource_type="Network",
                resource_id=str(network_id),
                message="Network not found"
            )
        return network
    except ResourceNotFoundError:
        # 既知の例外は再送
        raise
    except Exception as e:
        logger.error(f"Error getting network {network_id}: {e}", exc_info=True)
        raise DatabaseCommunicationError(
            message=f"Error getting network: {str(e)}",
            context={"network_id": network_id}
        )

def update_network_graphml(db: Session, network_id: int, graphml_content: str) -> Network:
    """
    ネットワークのGraphMLコンテンツを更新します。
    
    Args:
        db: データベースセッション
        network_id: ネットワークID
        graphml_content: 新しいGraphMLコンテンツ
        
    Returns:
        更新されたネットワークオブジェクト
        
    Raises:
        ResourceNotFoundError: ネットワークが見つからない場合
        DatabaseCommunicationError: データベース操作に失敗した場合
    """
    try:
        network = get_network(db, network_id)
        network.graphml_content = graphml_content
        db.commit()
        db.refresh(network)
        return network
    except ResourceNotFoundError:
        # 既知の例外は再送
        raise
    except Exception as e:
        logger.error(f"Error updating network {network_id} GraphML: {e}", exc_info=True)
        raise DatabaseCommunicationError(
            message=f"Error updating network GraphML: {str(e)}",
            context={"network_id": network_id}
        )

def update_layout_cache(db: Session, network_id: int, layout_type: str, positions: Dict[str, Dict[str, float]]) -> Network:
    """
    ネットワークのレイアウトキャッシュを更新します。
    
    Args:
        db: データベースセッション
        network_id: ネットワークID
        layout_type: レイアウトタイプ
        positions: 位置情報
        
    Returns:
        更新されたネットワークオブジェクト
        
    Raises:
        ResourceNotFoundError: ネットワークが見つからない場合
        DatabaseCommunicationError: データベース操作に失敗した場合
    """
    try:
        network = get_network(db, network_id)
        
        # 既存のキャッシュを読み込む
        try:
            layout_cache = json.loads(network.layout_cache)
        except (json.JSONDecodeError, TypeError):
            layout_cache = {}
        
        # キャッシュを更新
        layout_cache[layout_type] = positions
        network.layout_cache = json.dumps(layout_cache)
        
        db.commit()
        db.refresh(network)
        return network
    except ResourceNotFoundError:
        # 既知の例外は再送
        raise
    except Exception as e:
        logger.error(f"Error updating layout cache for network {network_id}: {e}", exc_info=True)
        raise DatabaseCommunicationError(
            message=f"Error updating layout cache: {str(e)}",
            context={"network_id": network_id, "layout_type": layout_type}
        )

def update_centrality_cache(db: Session, network_id: int, centrality_type: str, centrality_values: Dict[str, float]) -> Network:
    """
    ネットワークの中心性キャッシュを更新します。
    
    Args:
        db: データベースセッション
        network_id: ネットワークID
        centrality_type: 中心性タイプ
        centrality_values: 中心性値
        
    Returns:
        更新されたネットワークオブジェクト
        
    Raises:
        ResourceNotFoundError: ネットワークが見つからない場合
        DatabaseCommunicationError: データベース操作に失敗した場合
    """
    try:
        network = get_network(db, network_id)
        
        # 既存のキャッシュを読み込む
        try:
            centrality_cache = json.loads(network.centrality_cache)
        except (json.JSONDecodeError, TypeError):
            centrality_cache = {}
        
        # キャッシュを更新
        centrality_cache[centrality_type] = {
            "success": True,
            "centrality_type": centrality_type,
            "centrality_values": centrality_values
        }
        network.centrality_cache = json.dumps(centrality_cache)
        
        db.commit()
        db.refresh(network)
        return network
    except ResourceNotFoundError:
        # 既知の例外は再送
        raise
    except Exception as e:
        logger.error(f"Error updating centrality cache for network {network_id}: {e}", exc_info=True)
        raise DatabaseCommunicationError(
            message=f"Error updating centrality cache: {str(e)}",
            context={"network_id": network_id, "centrality_type": centrality_type}
        )

def get_layout_cache(db: Session, network_id: int, layout_type: str) -> Optional[Dict[str, Dict[str, float]]]:
    """
    ネットワークのレイアウトキャッシュを取得します。
    
    Args:
        db: データベースセッション
        network_id: ネットワークID
        layout_type: レイアウトタイプ
        
    Returns:
        キャッシュされた位置情報、キャッシュがない場合はNone
        
    Raises:
        ResourceNotFoundError: ネットワークが見つからない場合
        DatabaseCommunicationError: データベース操作に失敗した場合
    """
    try:
        network = get_network(db, network_id)
        
        # キャッシュを読み込む
        try:
            layout_cache = json.loads(network.layout_cache)
            return layout_cache.get(layout_type)
        except (json.JSONDecodeError, TypeError):
            return None
    except ResourceNotFoundError:
        # 既知の例外は再送
        raise
    except Exception as e:
        logger.error(f"Error getting layout cache for network {network_id}: {e}", exc_info=True)
        raise DatabaseCommunicationError(
            message=f"Error getting layout cache: {str(e)}",
            context={"network_id": network_id, "layout_type": layout_type}
        )

def get_centrality_cache(db: Session, network_id: int, centrality_type: str) -> Optional[Dict[str, Any]]:
    """
    ネットワークの中心性キャッシュを取得します。
    
    Args:
        db: データベースセッション
        network_id: ネットワークID
        centrality_type: 中心性タイプ
        
    Returns:
        キャッシュされた中心性値、キャッシュがない場合はNone
        
    Raises:
        ResourceNotFoundError: ネットワークが見つからない場合
        DatabaseCommunicationError: データベース操作に失敗した場合
    """
    try:
        network = get_network(db, network_id)
        
        # キャッシュを読み込む
        try:
            centrality_cache = json.loads(network.centrality_cache)
            return centrality_cache.get(centrality_type)
        except (json.JSONDecodeError, TypeError):
            return None
    except ResourceNotFoundError:
        # 既知の例外は再送
        raise
    except Exception as e:
        logger.error(f"Error getting centrality cache for network {network_id}: {e}", exc_info=True)
        raise DatabaseCommunicationError(
            message=f"Error getting centrality cache: {str(e)}",
            context={"network_id": network_id, "centrality_type": centrality_type}
        )
```

### 2. GraphML変換処理の専用モジュール化

#### 2.1 `graphml/converter.py`

GraphML変換機能を提供します。

```python
# NetworkXMCP/graphml/converter.py

from typing import Dict, Any
from common.utils.graphml.converter import convert_to_standard_graphml
from common.exceptions import GraphProcessingError
from common.logging.config import get_logger

logger = get_logger("networkx_mcp.graphml.converter")

def convert_graphml(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列を標準形式に変換します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: 変換結果
        
    Raises:
        GraphProcessingError: GraphMLの変換に失敗した場合
    """
    try:
        # 共通モジュールの変換関数を使用
        standardized_graphml = convert_to_standard_graphml(graphml_content)
        
        return {
            "success": True,
            "graphml_content": standardized_graphml
        }
    except Exception as e:
        logger.error(f"Error converting GraphML: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error converting GraphML: {str(e)}"
        }
```

#### 2.2 `graphml/validator.py`

GraphML検証機能を提供します。

```python
# NetworkXMCP/graphml/validator.py

from typing import Dict, Any, List
from common.utils.graphml.validator import validate_graphml_content, validate_graphml_structure
from common.exceptions import GraphMLValidationError
from common.logging.config import get_logger

logger = get_logger("networkx_mcp.graphml.validator")

def validate_graphml(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列を検証します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: 検証結果
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
    """
    try:
        # 共通モジュールの検証関数を使用
        validate_graphml_content(graphml_content)
        
        # 構造の警告を取得
        warnings = validate_graphml_structure(graphml_content)
        
        return {
            "success": True,
            "warnings": warnings
        }
    except GraphMLValidationError as e:
        logger.error(f"GraphML validation error: {e.message}")
        return {
            "success": False,
            "error": e.message,
            "validation_errors": e.validation_errors
        }
    except Exception as e:
        logger.error(f"Error validating GraphML: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error validating GraphML: {str(e)}"
        }
```

#### 2.3 `graphml/fixer.py`

GraphML修正機能を提供します。

```python
# NetworkXMCP/graphml/fixer.py

from typing import Dict, Any
from common.utils.graphml.fixer import fix_graphml_structure, add_missing_attributes
from common.exceptions import GraphProcessingError
from common.logging.config import get_logger

logger = get_logger("networkx_mcp.graphml.fixer")

def fix_graphml(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列を修正します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: 修正結果
        
    Raises:
        GraphProcessingError: GraphMLの修正に失敗した場合
    """
    try:
        # 共通モジュールの修正関数を使用
        fixed_graphml = fix_graphml_structure(graphml_content)
        
        # 不足している属性を追加
        fixed_graphml = add_missing_attributes(fixed_graphml)
        
        return {
            "success": True,
            "graphml_content": fixed_graphml
        }
    except Exception as e:
        logger.error(f"Error fixing GraphML: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error fixing GraphML: {str(e)}"
        }
```

### 3. tools/network_tools.pyの機能別分割

#### 3.1 `tools/creation.py`

ネットワーク作成機能を提供します。

```python
# NetworkXMCP/tools/creation.py

import networkx as nx
import numpy as np
import random
from typing import Dict, List, Any, Tuple, Optional

from common.logging.config import get_logger

logger = get_logger("networkx_mcp.tools.creation")

def create_random_network(num_nodes=20, edge_probability=0.2, seed=None) -> Tuple[nx.Graph, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    ランダムネットワークを作成します。
    
    Args:
        num_nodes: ネットワークのノード数
        edge_probability: 任意の2つのノード間のエッジの確率
        seed: 生成に使用する乱数シード
        
    Returns:
        Tuple[nx.Graph, List[Dict[str, Any]], List[Dict[str, Any]]]: NetworkXグラフ、ノードのリスト、エッジのリスト
    """
    try:
        # 乱数シードの設定
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # ランダムグラフを生成
        G = nx.gnp_random_graph(num_nodes, edge_probability, seed=seed)
        
        # 連結グラフを確保（孤立ノードがないようにする）
        if not nx.is_connected(G):
            # 連結成分を取得
            components = list(nx.connected_components(G))
            # 最大の連結成分以外の各成分から、最大成分へエッジを追加
            largest_component = max(components, key=len)
            for component in components:
                if component != largest_component:
                    # 各成分から最大成分へのエッジを追加
                    node_from = random.choice(list(component))
                    node_to = random.choice(list(largest_component))
                    G.add_edge(node_from, node_to)
        
        # ノードとエッジの情報を抽出
        nodes = []
        for node in G.nodes():
            # ノードごとに少し異なるサイズと色の変化をつける
            size_variation = random.uniform(4.5, 5.5)
            color_variation = random.randint(-15, 15)
            base_color = [29, 78, 216]  # #1d4ed8のRGB値
            
            # 色の変化を適用（範囲内に収める）
            r = max(0, min(255, base_color[0] + color_variation))
            g = max(0, min(255, base_color[1] + color_variation))
            b = max(0, min(255, base_color[2] + color_variation))
            
            nodes.append({
                "id": str(node),
                "label": f"Node {node}",
                "size": size_variation,
                "color": f"rgb({r}, {g}, {b})"
            })
        
        edges = []
        for edge in G.edges():
            edges.append({
                "source": str(edge[0]),
                "target": str(edge[1]),
                "width": 1,
                "color": "#94a3b8"
            })
        
        # スプリングレイアウトを適用
        pos = nx.spring_layout(G)
        
        # ノードの位置情報を追加
        for node in nodes:
            node_id = int(node["id"])
            if node_id in pos:
                node["x"] = float(pos[node_id][0])
                node["y"] = float(pos[node_id][1])
        
        return G, nodes, edges
    except Exception as e:
        logger.error(f"Error creating random network: {e}", exc_info=True)
        return None, [], []
```

#### 3.2 `tools/parsing.py`

ネットワークパース機能を提供します。

```python
# NetworkXMCP/tools/parsing.py

import networkx as nx
import io
from typing import Dict, List, Any, Optional

from common.exceptions import GraphMLValidationError
from common.logging.config import get_logger

logger = get_logger("networkx_mcp.tools.parsing")

def parse_graphml_string(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列をパースし、グラフデータを抽出します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: パース結果
    """
    try:
        # Parse the GraphML content
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)
        
        # Extract nodes and edges
        nodes = []
        for node in G.nodes(data=True):
            node_id = str(node[0])
            attrs = node[1]
            
            node_data = {
                "id": node_id,
                "label": attrs.get("name", node_id)
            }
            
            # Add position if available
            if 'x' in attrs and 'y' in attrs:
                try:
                    node_data['x'] = float(attrs['x'])
                    node_data['y'] = float(attrs['y'])
                except (ValueError, TypeError):
                    pass
            
            # Add size if available
            if 'size' in attrs:
                try:
                    node_data['size'] = float(attrs['size'])
                except (ValueError, TypeError):
                    node_data['size'] = 5.0
            
            # Add color if available
            if 'color' in attrs:
                node_data['color'] = attrs['color']
            
            # Add any additional node attributes
            for key, value in attrs.items():
                if key not in ["id", "label", "x", "y", "size", "color", "name"]:
                    node_data[key] = value
            
            nodes.append(node_data)
        
        edges = []
        for edge in G.edges(data=True):
            source = str(edge[0])
            target = str(edge[1])
            attrs = edge[2]
            
            edge_data = {
                "source": source,
                "target": target
            }
            
            # Add width if available
            if 'width' in attrs:
                try:
                    edge_data['width'] = float(attrs['width'])
                except (ValueError, TypeError):
                    pass
            
            # Add color if available
            if 'color' in attrs:
                edge_data['color'] = attrs['color']
            
            # Add any additional edge attributes
            for key, value in attrs.items():
                if key not in ["source", "target", "width", "color"]:
                    edge_data[key] = value
            
            edges.append(edge_data)
        
        # Extract graph attributes
        attributes = {}
        for key, value in G.graph.items():
            attributes[key] = value
        
        return {
            "success": True,
            "graph": G,
            "nodes": nodes,
            "edges": edges,
            "attributes": attributes,
            "directed": G.is_directed()
        }
    except Exception as e:
        logger.error(f"Error parsing GraphML string: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error parsing GraphML string: {str(e)}"
        }
```

#### 3.3 `tools/export.py`

ネットワークエクスポート機能を提供します。

```python
# NetworkXMCP/tools/export.py

import networkx as nx
import io
from typing import Dict, List, Any, Optional

from common.logging.config import get_logger

logger = get_logger("networkx_mcp.tools.export")

def export_network_as_graphml(G, positions=None, visual_properties=None) -> Dict[str, Any]:
    """
    NetworkXグラフをGraphML形式にエクスポートします。
    
    Args:
        G: NetworkXグラフ
        positions: ノードの位置情報
        visual_properties: グラフの視覚的プロパティ
        
    Returns:
        Dict[str, Any]: エクスポート結果
    """
    try:
        # Create a copy of the graph to avoid modifying the original
        export_G = G.copy()
        
        # Add standard node attributes (name, color, size, description) if not present
        for node in export_G.nodes():
            node_str = str(node)
            
            # Set default attributes if not present
            if 'name' not in export_G.nodes[node]:
                export_G.nodes[node]['name'] = node_str
                
            if 'size' not in export_G.nodes[node]:
                export_G.nodes[node]['size'] = "5.0"  # Default size
                
            if 'color' not in export_G.nodes[node]:
                export_G.nodes[node]['color'] = "#1d4ed8"  # Default color
                
            if 'description' not in export_G.nodes[node]:
                export_G.nodes[node]['description'] = f"Node {node_str}"
        
        # Add positions if provided
        if positions:
            pos_dict = {}
            for node_pos in positions:
                node_id = node_pos["id"]
                if node_id.isdigit():
                    try:
                        node_id = int(node_id)
                    except:
                        pass
                
                if node_id in export_G.nodes():
                    # Add position attributes
                    export_G.nodes[node_id]['x'] = str(node_pos.get('x', 0.0))
                    export_G.nodes[node_id]['y'] = str(node_pos.get('y', 0.0))
                    
                    # Add other visual attributes if present
                    if 'size' in node_pos:
                        export_G.nodes[node_id]['size'] = str(node_pos['size'])
                    if 'color' in node_pos:
                        export_G.nodes[node_id]['color'] = node_pos['color']
                    if 'label' in node_pos:
                        export_G.nodes[node_id]['name'] = node_pos['label']
        
        # Add global visual properties if provided
        if visual_properties:
            # Add graph-level attributes
            export_G.graph['node_default_size'] = str(visual_properties.get('node_size', 5))
            export_G.graph['node_default_color'] = visual_properties.get('node_color', '#1d4ed8')
            export_G.graph['edge_default_width'] = str(visual_properties.get('edge_width', 1))
            export_G.graph['edge_default_color'] = visual_properties.get