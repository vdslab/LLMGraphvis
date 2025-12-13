# 3. ネットワーク計算サービス仕様 (NetworkXAPI)

**前提知識レベル:**
- マイクロサービスの概念
- NetworkXライブラリに関する知識
- FastAPIに関する開発経験

NetworkXAPIは、ネットワークに関する計算処理と、その結果の永続化に特化した**MCP (Model Context Protocol) サーバー**です。FastAPI上で動作し、SSE (Server-Sent Events) を通じてツールを公開します。

## 3.1. 役割

- **MCP Server**: GenAIのための標準化されたインターフェース（MCP）を提供し、Tools (Act), Resources (Read), Prompts (Template) を通じて機能を提供する。
- **ステートレス計算**: 内部状態を持たず、計算結果は全てデータベースに永続化する。
- **SSEエンドポイント**: `/mcp/sse` エンドポイントを通じてMCPプロトコルによる通信を行う。

## 3.2. ツール定義 (MCP Tools)

本サーバーが提供するMCPツール、およびクライアント側（Backend）で提供されるユーティリティツールの定義です。

### 3.2.0. Client-Side Utility Tools (Backend提供)

これらはNetworkXAPIサーバー自体には実装されていませんが、MCPクライアント(Backend)がアダプターとして提供し、LLMが利用可能なツールです。

#### `read_resource(uri: str)`
- **説明**: MCPサーバー上のリソース（データ）を直接読み込みます。LLMは計算や可視化を行う前に、このツールを使ってデータの存在や内容（例：属性リスト）を確認することが義務付けられています。
- **引数**:
  - `uri`: リソースURI (例: `network://1/attributes/nodes`)

### 3.2.1. Server-Side MCP Tools (NetworkXAPI提供)

モデルが**アクション**を起こすために使用する関数群です。副作用（DB更新、計算実行など）を伴う操作は全てツールとして定義します。

| Tool Name | 説明 |
|:---|:---|
| `initialize_network` | GraphMLデータを受け取り、初期化を行う。**指定された`network_id`に既にデータ（ノード）が存在する場合は、上書きせずに新しい`network_id`を発行して新規ネットワークとして保存する。** 処理内容は、1.正規化、2.DB保存、3.初期レイアウト(Spring)計算、4.初期レンダリングデータ生成。レスポンスには最終的に使用された`network_id`が含まれる。 |
| `update_network_metadata` | ネットワークの名前や説明（description）を更新する。LLMがネットワークのコンテキスト（例：「これは空手クラブの相関図です」）を理解・保持するために使用する。 |
| `calculate_centrality` | 中心性指標を計算して永続化する。具体的には、まず属性の**定義**（例: 'degree_centrality'）が`node_attributes`に存在するか確認し、なければ`network_id`に紐付けて作成する。次に、各ノードの計算**値**を、定義のIDを参照して`node_attribute_values`に保存する。レスポンスは計算完了のステータスのみを返す。 |
| `calculate_layout` | レイアウト座標を計算して永続化する。`layout_name`（例: 'forceatlas2', 'spiral'）を受け取り、`{layout_name}_x`, `{layout_name}_y` という属性として保存する。レスポンスは計算完了のステータスのみを返す。 |
| `generate_visualization` | レイアウト、ノードサイズ、ノードカラー等の視覚的割り当てに関するすべてのパラメータを受け取り、最終的なレンダリングデータを動的に生成して返す。**レイアウト計算は行わず、計算済みの座標データを使用する。新しいレイアウトを適用する場合や、中心性指標などを利用する場合は、事前に`calculate_layout`や`calculate_centrality`を呼び出す必要がある。** 指定された属性やレイアウトが存在しない場合はエラーを返す。サブグラフのオーバーレイ表示もサポートする。 |
| `create_ego_network` | 指定されたノードを中心としたEgo Graph（指定ホップ数以内のノード群）を新しいネットワークとして作成する。**同じ条件（中心ノード、半径）で作成されたサブグラフが既に存在する場合は、新規作成せずに既存のネットワークを再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_subgraph_from_nodes` | 指定されたノードIDのリストからサブグラフを新しいネットワークとして作成する。**ノードリストに基づいて一意な名前（`Subgraph (A,B,...)`）を生成し、同名のサブグラフが存在する場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_path_subgraph` | 指定された2ノード間の最短経路をサブグラフとして新しいネットワークとして作成する。**既存のパスサブグラフがある場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_k_core_subgraph` | K-Core（次数k以上のノード群）を抽出し、新しいネットワークとして作成する。**同じk値のK-Coreサブグラフがある場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_largest_component_subgraph` | 最大連結成分を抽出し、新しいネットワークとして作成する。**既に作成済みの場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_component_containing_node` | 指定されたノードを含む連結成分を抽出し、新しいネットワークとして作成する。**既に作成済みの場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_subgraph_by_attribute_filter` | ノード属性の条件（範囲、カテゴリ、複合）に基づいてフィルタリングを行い、一致するノード群でサブグラフを作成する。**レスポンスは辞書形式で、`network_id`を含む。** |

## 3.3. MCPリソース一覧 (Resources)

モデルが**参照**する読み取り専用データです。クライアント（LLM Service）は `read_resource(uri)` ツールを通じてこれらにアクセスします。
 
| Resource URI | 説明 |
|:---|:---|
| `network://{id}/metadata` | ネットワークのメタデータ（ID, 名前, 説明, 作成日時）をJSON形式で取得する。 |
| `network://{id}/graphml` | ネットワークの完全なGraphMLデータを取得する。 |
| `network://{id}/attributes/nodes` | 利用可能なノード属性（名前, 型, 統計情報）の一覧を取得する。 |
| `network://{id}/attributes/edges` | 利用可能なエッジ属性（名前, 型, 統計情報）の一覧を取得する。 |
| `network://{id}/subgraphs` | 親ネットワークから作成されたサブグラフの一覧を取得する。 |
| `network://{id}/centrality/{metric}/top` | 指定された中心性指標（metric）の上位ノードを取得する。オプションパラメータには対応しないため、デフォルト設定（TOP 10）等を返す。 |
| `network://{id}/structure` | ネットワークの基本構造情報（ノード数、エッジ数、密度、連結成分数など）を取得する。 |

## 3.4. MCPプロンプト一覧 (Prompts)

モデルに対する**定型的な指示セット**です。分析の開始点や、特定のタスク（可視化提案など）を行う際に使用されます。

| Prompt Name | Arguments | 説明 |
|:---|:---|:---|
| `analyze-structure` | `network_id` | ネットワークの構造的特徴（密度、連結性など）を分析し、全体像を把握するよう指示するメッセージセットを返す。 |
| `recommend-visualization` | `network_id` | 利用可能な属性と構造に基づいて、最適な可視化（レイアウト、色、サイズ）を提案するよう指示するメッセージセットを返す。 |
| `investigate-attributes` | `network_id` | 特定のノードやエッジの属性に注目し、異常値や特徴的なパターンを探すよう指示するメッセージセットを返す。 |
| `find-important-nodes` | `network_id` | 複数の中心性指標や属性を組み合わせて、ネットワーク内の重要ノード（インフルエンサー、ハブなど）を特定し、その理由を説明するよう指示するメッセージセットを返す。 |
| `search_nodes` | `network_id`, `query`, `attribute` | ノード名（ID、ラベル）または特定の属性値でノードを検索する。検索結果には、マッチした値も含まれる。 |

## 3.5. ツール定義詳細

### `initialize_network`
- **Description**: GraphMLデータを受け取り、初期化（パース、DB保存、初期レイアウト計算、初期レンダリングデータ生成）を行う。
- **Arguments**:
  - `network_id`: int
  - `graphml_data`: str
- **Returns**: `{"network": dict, "network_id": int}`

### `update_network_metadata`
- **Description**: ネットワークの名前や説明を更新する。
- **Arguments**:
  - `network_id`: int
  - `description`: str (Optional)
  - `name`: str (Optional)

### `calculate_centrality`
- **Description**: 指定された中心性指標を計算し、ノード属性として保存する。
- **Arguments**:
  - `network_id`: int
  - `centrality_type`: str ("degree", "betweenness", "closeness", "eigenvector")

### `calculate_layout`
- **Description**: 指定されたレイアウトアルゴリズムで座標を計算し、ノード属性として保存する。
- **Arguments**:
  - `network_id`: int
  - `layout_name`: str ("spring", "forceatlas2", "circular", "kamada_kawai", "shell", "spectral", "spiral")

### `create_ego_network`
- **Description**: 指定ノードを中心としたEgo Graphを作成する。
- **Arguments**:
  - `source_network_id`: int
  - `center_node_id`: str
  - `radius`: int
- **Returns**: `{"network_id": int, "name": str}`

### `create_subgraph_from_nodes`
- **Description**: ノードIDリストからサブグラフを作成する。
- **Arguments**:
  - `source_network_id`: int
  - `node_ids`: List[str]
- **Returns**: `{"network_id": int, "name": str}`

### `create_path_subgraph`
- **Description**: 最短経路のサブグラフを作成する。
- **Arguments**:
  - `source_network_id`: int
  - `source_node_id`: str
  - `target_node_id`: str
- **Returns**: `{"network_id": int, "name": str}`

### `create_k_core_subgraph`
- **Description**: K-Coreサブグラフを作成する。
- **Arguments**:
  - `source_network_id`: int
  - `k`: int
- **Returns**: `{"network_id": int, "name": str}`

### `create_largest_component_subgraph`
- **Description**: 最大連結成分のサブグラフを作成する。
- **Arguments**:
  - `source_network_id`: int
- **Returns**: `{"network_id": int, "name": str}`

### `create_component_containing_node`
- **Description**: 指定ノードを含む連結成分のサブグラフを作成する。
- **Arguments**:
  - `source_network_id`: int
  - `node_id`: str
- **Returns**: `{"network_id": int, "name": str}`

### `create_subgraph_by_attribute_filter`
- **Description**: 属性フィルタ条件に基づいてサブグラフを作成する。
- **Arguments**:
  - `network_id`: int
  - `conditions`: List[dict] (e.g., `[{"attribute_name": "Age", "ranges": [{"min": 10, "max": 20}]}, {"attribute_name": "Gender", "categories": ["F"]}]`)
  - `suffix`: str (Optional)
- **Returns**: `{"network_id": int, "name": str}`

### `generate_visualization`
- **Arguments**:
  - `network_id`: int
  - `focus_network_id`: int (Optional)
  - `node_size_config`: dict (Optional)
  - `node_color_config`: dict (Optional)
  - `edge_width_config`: dict (Optional)
  - `context_config`: dict (Optional)
  - `focus_config`: dict (Optional)
  - `node_label_config`: dict (Optional)
  - `custom_node_colors`: list[dict] (Optional)

**Config Pattern:** Keys correspond to the API implementation. Use `generate_visualization` carefully to create rich, meaningful visualizations.

**Node Coloring Examples:**
- **Categorical with map**: `node_color_config={"scale_type": "CATEGORICAL", "attribute": "Country", "color_map": {"USA": "blue", "Japan": "red"}}` (Others will be auto-colored)
- **Categorical with map and fallback**: `node_color_config={"scale_type": "CATEGORICAL", "attribute": "Country", "color_map": {"USA": "blue"}, "default_color": "gray"}` (Others will be gray)

## 3.6. REST API エンドポイント (MCP Feature Parity)

MCPツールと同等の機能をREST API経由でも利用可能にするため、以下のエンドポイントを提供します。これらは `endpoints/networks.py`, `endpoints/subgraphs.py` 等で定義されています。

### ネットワーク管理 (`/api/v1/networks`)

| Method | Path | 説明 |
| :----- | :--- | :--- |
| `POST` | `/initialize` | GraphMLデータを受け取り、ネットワークを初期化（パース、保存、初期レイアウト計算）する。 |
| `GET` | `/{network_id}/metadata` | ネットワークのメタデータ（名前、説明、視覚状態）を取得する。 |
| `PUT` | `/{network_id}/metadata` | ネットワークのメタデータを更新する。 |
| `GET` | `/{network_id}/export` | ネットワークをGraphML形式でエクスポートする。 |

### ネットワーク分析・検索 (`/api/v1/networks`)

| Method | Path | 説明 |
| :----- | :--- | :--- |
| `GET` | `/{network_id}/attributes/nodes` | 利用可能なノード属性（統計情報含む）の一覧を取得する。 |
| `GET` | `/{network_id}/attributes/edges` | 利用可能なエッジ属性（統計情報含む）の一覧を取得する。 |
| `GET` | `/{network_id}/nodes/search` | クエリ文字列または属性値でノードを検索する。 |
| `GET` | `/{network_id}/subgraphs` | ネットワークから派生したサブグラフの一覧を取得する。 |

### サブグラフ作成 (`/api/v1/networks/{network_id}/subgraphs`)

| Method | Path | 説明 |
| :----- | :--- | :--- |
| `POST` | `/ego` | Ego Networkを作成する。 |
| `POST` | `/from-nodes` | 指定ノード群からサブグラフを作成する。 |
| `POST` | `/path` | 最短経路サブグラフを作成する。 |
| `POST` | `/k-core` | K-Coreサブグラフを作成する。 |
| `POST` | `/largest-component` | 最大連結成分サブグラフを作成する。 |
| `POST` | `/component-containing-node` | 指定ノードを含む連結成分サブグラフを作成する。 |
| `POST` | `/filter` | 属性条件に基づいてノードをフィルタリングし、サブグラフを作成する。 |

