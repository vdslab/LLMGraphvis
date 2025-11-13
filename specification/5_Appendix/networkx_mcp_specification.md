# NetworkXMCP機能仕様書

## 概要

NetworkXMCPは、LLMGraphvisプロジェクトのバックエンドサービスとして、ネットワーク分析と可視化機能を提供するMCP（Model Context Protocol）サーバーです。このサービスは、NetworkXライブラリを使用してグラフデータの処理、レイアウト計算、中心性指標の計算などを行います。また、計算結果をキャッシュすることで、パフォーマンスを向上させています。

## アーキテクチャ

NetworkXMCPは、以下のコンポーネントで構成されています。

```
NetworkXMCP/
  ├── api/            # APIエンドポイント
  ├── database/       # データベース関連
  ├── graphml/        # GraphML処理
  ├── tools/          # ネットワーク処理ツール
  ├── layouts/        # レイアウトアルゴリズム
  ├── metrics/        # 中心性指標計算
  ├── cache/          # キャッシュ管理
  ├── core/           # コア機能
  └── main.py         # エントリーポイント
```

## 機能一覧

NetworkXMCPは、以下の主要な機能を提供します。

1. **GraphML処理**
   - GraphMLファイルの検証
   - GraphMLファイルの変換
   - GraphMLファイルの修正

2. **レイアウト計算**
   - 各種レイアウトアルゴリズムの提供
   - レイアウト結果のキャッシュ

3. **中心性指標計算**
   - 各種中心性指標の計算
   - 中心性指標結果のキャッシュ

4. **ネットワーク分析**
   - ネットワーク統計情報の計算
   - コミュニティ検出
   - パス分析

## APIエンドポイント

### ヘルスチェック

```
GET /health
```

**レスポンス**:

```json
{
  "status": "ok"
}
```

### GraphML変換

```
POST /tools/convert_graphml
```

**リクエスト**:

```json
{
  "graphml_content": "<graphml>...</graphml>"
}
```

**レスポンス**:

```json
{
  "success": true,
  "graphml_content": "<graphml>...</graphml>"
}
```

### レイアウト計算

```
POST /tools/change_layout
```

**リクエスト**:

```json
{
  "network_id": 1,
  "layout_type": "spring",
  "layout_params": {
    "k": 0.3,
    "iterations": 100
  }
}
```

**レスポンス**:

```json
{
  "result": {
    "success": true,
    "layout_type": "spring",
    "positions": {
      "1": {
        "x": 0.5,
        "y": 0.3
      },
      "2": {
        "x": 0.7,
        "y": 0.2
      },
      ...
    }
  }
}
```

### 中心性計算

```
POST /tools/calculate_centrality
```

**リクエスト**:

```json
{
  "network_id": 1,
  "centrality_type": "degree",
  "centrality_params": {}
}
```

**レスポンス**:

```json
{
  "result": {
    "success": true,
    "centrality_type": "degree",
    "centrality_values": {
      "1": 0.8,
      "2": 0.5,
      ...
    }
  }
}
```

## GraphML処理

### GraphML検証

GraphMLファイルの検証を行います。検証では、以下の項目をチェックします。

- XMLとしての妥当性
- GraphML要素の存在
- 必須属性の存在

```python
def validate_graphml(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列を検証します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: 検証結果
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
        return {
            "success": False,
            "error": e.message,
            "validation_errors": e.validation_errors
        }
```

### GraphML変換

GraphMLファイルを標準形式に変換します。変換では、以下の処理を行います。

- 構造の修正
- 標準属性の追加
- 中心性指標の計算と追加

```python
def convert_graphml(graphml_content: str) -> Dict[str, Any]:
    """
    GraphML文字列を標準形式に変換します。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        Dict[str, Any]: 変換結果
    """
    try:
        # 共通モジュールの変換関数を使用
        standardized_graphml = convert_to_standard_graphml(graphml_content)
        
        return {
            "success": True,
            "graphml_content": standardized_graphml
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error converting GraphML: {str(e)}"
        }
```

## レイアウトアルゴリズム

NetworkXMCPは、以下のレイアウトアルゴリズムを提供します。

| アルゴリズム名 | 説明 | パラメータ |
|--------------|------|-----------|
| spring | バネモデルに基づくレイアウト | k, pos, fixed, iterations, threshold, weight, scale, center, dim, seed |
| circular | 円形レイアウト | scale, center, dim |
| random | ランダムレイアウト | center, dim, seed |
| spectral | スペクトルレイアウト | weight, scale, center, dim |
| shell | シェルレイアウト | nlist, scale, center, dim |
| kamada_kawai | Kamada-Kawaiアルゴリズムに基づくレイアウト | dist, pos, weight, scale, center, dim |
| fruchterman_reingold | Fruchterman-Reingoldアルゴリズムに基づくレイアウト | k, pos, fixed, iterations, threshold, weight, scale, center, dim, seed |
| spiral | スパイラルレイアウト | scale, center, dim, resolution, equidistant |
| multipartite | 多部グラフレイアウト | subset_key, align, scale, center |
| bipartite | 二部グラフレイアウト | nodes, align, scale, center |

### レイアウト計算の例

```python
def calculate_spring_layout(G, k=None, pos=None, fixed=None, iterations=50, threshold=1e-4, weight='weight', scale=1.0, center=None, dim=2, seed=None):
    """
    スプリングレイアウトを計算します。
    
    Args:
        G: NetworkXグラフ
        k: ノード間の最適距離
        pos: ノードの初期位置
        fixed: 固定するノード
        iterations: アルゴリズムの反復回数
        threshold: アルゴリズムの停止閾値
        weight: エッジの重みに使用するエッジ属性
        scale: レイアウトのスケール
        center: レイアウトの中心
        dim: レイアウトの次元
        seed: 乱数シード
        
    Returns:
        ノードIDをキー、位置を値とする辞書
    """
    try:
        return nx.spring_layout(G, k=k, pos=pos, fixed=fixed, iterations=iterations, threshold=threshold, weight=weight, scale=scale, center=center, dim=dim, seed=seed)
    except Exception as e:
        logger.error(f"Error calculating spring layout: {e}")
        # フォールバック: ランダムレイアウト
        return nx.random_layout(G, center=center, dim=dim, seed=seed)
```

## 中心性指標

NetworkXMCPは、以下の中心性指標を提供します。

| 指標名 | 説明 | パラメータ |
|-------|------|-----------|
| degree | 次数中心性 | - |
| closeness | 近接中心性 | - |
| betweenness | 媒介中心性 | k, normalized, weight, endpoints, seed |
| eigenvector | 固有ベクトル中心性 | max_iter, tol, nstart, weight |
| pagerank | PageRank | alpha, personalization, max_iter, tol, nstart, weight, dangling |
| katz | Katz中心性 | alpha, beta, max_iter, tol, nstart, normalized, weight |
| load | 負荷中心性 | v, cutoff, normalized, weight |
| harmonic | 調和中心性 | nbunch, distance, weight |
| subgraph | 部分グラフ中心性 | - |
| communicability_betweenness | 通信可能性媒介中心性 | normalized |

### 中心性計算の例

```python
def calculate_degree_centrality(G):
    """
    次数中心性を計算します。
    
    Args:
        G: NetworkXグラフ
        
    Returns:
        ノードIDをキー、中心性値を値とする辞書
    """
    try:
        return nx.degree_centrality(G)
    except Exception as e:
        logger.error(f"Error calculating degree centrality: {e}")
        return {}
```

## キャッシュ管理

NetworkXMCPは、レイアウト計算と中心性計算の結果をキャッシュすることで、パフォーマンスを向上させています。キャッシュは、データベースに保存されます。

### レイアウトキャッシュ

```python
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
    except Exception as e:
        logger.error(f"Error updating layout cache: {e}")
        raise
```

### 中心性キャッシュ

```python
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
    except Exception as e:
        logger.error(f"Error updating centrality cache: {e}")
        raise
```

## エラーハンドリング

NetworkXMCPは、共通例外クラスを使用して、一貫したエラーハンドリングを提供します。エラーが発生した場合、以下の形式でエラーレスポンスを返します。

```json
{
  "success": false,
  "error_code": "ERROR_CODE",
  "message": "Error message",
  "context": {
    "key1": "value1",
    "key2": "value2"
  },
  "timestamp": "2025-11-13T05:27:00.000Z"
}
```

### 主なエラーコード

| エラーコード | 説明 | HTTPステータスコード |
|------------|------|-------------------|
| `VALIDATION_ERROR` | リクエストの検証に失敗した | 400 |
| `GRAPHML_VALIDATION_ERROR` | GraphMLの検証に失敗した | 400 |
| `GRAPH_PROCESSING_ERROR` | グラフ処理に失敗した | 500 |
| `RESOURCE_NOT_FOUND_ERROR` | リソースが見つからない | 404 |
| `DATABASE_COMMUNICATION_ERROR` | データベースとの通信に失敗した | 503 |
| `INTERNAL_SERVER_ERROR` | サーバー内部エラー | 500 |

## データモデル

### Network

```python
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

### Conversation

```python
class Conversation(Base):
    """
    会話モデル。
    """
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
```

## 設定

NetworkXMCPは、環境変数を使用して設定を行います。

| 環境変数 | 説明 | デフォルト値 |
|---------|------|------------|
| `DATABASE_URL` | データベース接続URL | postgresql://postgres:postgres@db:5432/graphvis |
| `LOG_LEVEL` | ログレベル | INFO |
| `LOG_FORMAT` | ログ形式 | standard |
| `LOG_FILE` | ログファイルのパス | なし |

## 依存関係

NetworkXMCPは、以下の主要なライブラリに依存しています。

- NetworkX: グラフ処理
- FastAPI: APIフレームワーク
- SQLAlchemy: ORM
- Pydantic: データ検証
- httpx: HTTP通信

## パフォーマンス考慮事項

### キャッシュ戦略

NetworkXMCPは、レイアウト計算と中心性計算の結果をキャッシュすることで、パフォーマンスを向上させています。キャッシュは、以下の戦略で管理されます。

1. **キャッシュキー**: ネットワークID + レイアウトタイプ/中心性タイプ
2. **キャッシュ無効化**: ネットワークが更新された場合、関連するキャッシュは無効化される
3. **キャッシュ期限**: キャッシュに期限は設定されていない（ネットワークが更新されない限り永続的）

### 大規模グラフの処理

大規模グラフを処理する場合、以下の点に注意が必要です。

1. **メモリ使用量**: 大規模グラフはメモリを大量に消費する可能性がある
2. **計算時間**: 一部のアルゴリズムは大規模グラフで計算時間が長くなる可能性がある
3. **タイムアウト**: 長時間実行されるリクエストはタイムアウトする可能性がある

これらの問題に対処するため、以下の対策を実装しています。

1. **非同期処理**: 長時間実行される処理は非同期で実行
2. **部分計算**: 大規模グラフでは、一部のノードのみを対象に計算
3. **近似アルゴリズム**: 一部の中心性指標では、近似アルゴリズムを使用

## 拡張性

NetworkXMCPは、以下の方法で拡張できます。

### 新しいレイアウトアルゴリズムの追加

1. `layouts/layout_functions.py` に新しいレイアウト関数を追加
2. `get_layout_function` 関数に新しいレイアウトを登録

```python
def calculate_new_layout(G, param1=default1, param2=default2, ...):
    """
    新しいレイアウトアルゴリズム。
    
    Args:
        G: NetworkXグラフ
        param1: パラメータ1
        param2: パラメータ2
        
    Returns:
        ノードIDをキー、位置を値とする辞書
    """
    # レイアウト計算ロジック
    positions = {}
    # ...
    return positions

def get_layout_function(layout_type):
    """
    レイアウトタイプに対応するレイアウト関数を取得します。
    
    Args:
        layout_type: レイアウトタイプ
        
    Returns:
        レイアウト関数
    """
    layout_functions = {
        # 既存のレイアウト
        "spring": calculate_spring_layout,
        # ...
        
        # 新しいレイアウト
        "new_layout": calculate_new_layout
    }
    
    return layout_functions.get(layout_type, calculate_spring_layout)
```

### 新しい中心性指標の追加

1. `metrics/centrality_functions.py` に新しい中心性関数を追加
2. `get_centrality_function` 関数に新しい中心性を登録

```python
def calculate_new_centrality(G, param1=default1, param2=default2, ...):
    """
    新しい中心性指標。
    
    Args:
        G: NetworkXグラフ
        param1: パラメータ1
        param2: パラメータ2
        
    Returns:
        ノードIDをキー、中心性値を値とする辞書
    """
    # 中心性計算ロジック
    centrality = {}
    # ...
    return centrality

def get_centrality_function(centrality_type):
    """
    中心性タイプに対応する中心性関数を取得します。
    
    Args:
        centrality_type: 中心性タイプ
        
    Returns:
        中心性関数
    """
    centrality_functions = {
        # 既存の中心性
        "degree": calculate_degree_centrality,
        # ...
        
        # 新しい中心性
        "new_centrality": calculate_new_centrality
    }
    
    return centrality_functions.get(centrality_type, calculate_degree_centrality)
```

## 使用例

### GraphML変換

```python
import httpx

async def convert_graphml_example():
    url = "http://localhost:8001/tools/convert_graphml"
    payload = {
        "graphml_content": "<graphml>...</graphml>"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        
    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            print(f"Converted GraphML: {result.get('graphml_content')[:100]}...")
        else:
            print(f"Error: {result.get('error')}")
    else:
        print(f"Error: {response.text}")
```

### レイアウト計算

```python
import httpx

async def calculate_layout_example():
    url = "http://localhost:8001/tools/change_layout"
    payload = {
        "network_id": 1,
        "layout_type": "spring",
        "layout_params": {
            "k": 0.3,
            "iterations": 100
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        
    if response.status_code == 200:
        result = response.json()
        if result.get("result", {}).get("success"):
            print(f"Layout calculated: {result.get('result', {}).get('layout_type')}")
            print(f"Positions: {len(result.get('result', {}).get('positions', {}))} nodes")
        else:
            print(f"Error: {result.get('result', {}).get('error')}")
    else:
        print(f"Error: {response.text}")
```

### 中心性計算

```python
import httpx

async def calculate_centrality_example():
    url = "http://localhost:8001/tools/calculate_centrality"
    payload = {
        "network_id": 1,
        "centrality_type": "degree",
        "centrality_params": {}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        
    if response.status_code == 200:
        result = response.json()
        if result.get("result", {}).get("success"):
            print(f"Centrality calculated: {result.get('result', {}).get('centrality_type')}")
            print(f"Values: {len(result.get('result', {}).get('centrality_values', {}))} nodes")
        else:
            print(f"Error: {result.get('result', {}).get('error')}")
    else:
        print(f"Error: {response.text}")