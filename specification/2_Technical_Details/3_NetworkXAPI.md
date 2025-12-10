# 3. ネットワーク計算サービス仕様 (NetworkXAPI)

**前提知識レベル:**
- マイクロサービスの概念
- NetworkXライブラリに関する知識
- FastAPIに関する開発経験

NetworkXAPIは、ネットワークに関する計算処理と、その結果の永続化に特化した**MCP (Model Context Protocol) サーバー**です。FastAPI上で動作し、SSE (Server-Sent Events) を通じてツールを公開します。

## 3.1. 役割

- **MCP Server**: GenAIのための標準化されたインターフェース（MCP）を提供し、LLMが直接的にツールを認識・実行できる環境を提供する。
- **ステートレス計算**: 内部状態を持たず、計算結果は全てデータベースに永続化する。
- **SSEエンドポイント**: `/mcp/sse` エンドポイントを通じてMCPプロトコルによる通信を行う。既存のRESTエンドポイントはMCPツールに置き換えられる。

## 3.2. MCPツール一覧

`API`サービス（MCP Client）から呼び出される、主要なツールです。

| Tool Name | 説明 |
|:---|:---|
| `initialize_network` | GraphMLデータを受け取り、初期化を行う。**指定された`network_id`に既にデータ（ノード）が存在する場合は、上書きせずに新しい`network_id`を発行して新規ネットワークとして保存する。** 処理内容は、1.正規化、2.DB保存、3.初期レイアウト(Spring)計算、4.初期レンダリングデータ生成。レスポンスには最終的に使用された`network_id`が含まれる。 |
| `update_network_metadata` | ネットワークの名前や説明（description）を更新する。LLMがネットワークのコンテキスト（例：「これは空手クラブの相関図です」）を理解・保持するために使用する。 |
| `list_node_attributes` | ネットワークに存在するノード属性（計算済みまたは元から存在）の一覧を返す。 |
| `list_edge_attributes` | ネットワークに存在するエッジ属性（計算済みまたは元から存在）の一覧を返す。 |
| `calculate_centrality` | 中心性指標を計算して永続化する。具体的には、まず属性の**定義**（例: 'degree_centrality'）が`node_attributes`に存在するか確認し、なければ`network_id`に紐付けて作成する。次に、各ノードの計算**値**を、定義のIDを参照して`node_attribute_values`に保存する。レスポンスは計算完了のステータスのみを返す。 |
| `calculate_layout` | レイアウト座標を計算して永続化する。`layout_name`（例: 'forceatlas2', 'spiral'）を受け取り、`{layout_name}_x`, `{layout_name}_y` という属性として保存する。レスポンスは計算完了のステータスのみを返す。 |
| `generate_visualization` | レイアウト、ノードサイズ、ノードカラー等の視覚的割り当てに関するすべてのパラメータを受け取り、最終的なレンダリングデータを動的に生成して返す。**レイアウト計算は行わず、計算済みの座標データを使用する。新しいレイアウトを適用する場合や、中心性指標などを利用する場合は、事前に`calculate_layout`や`calculate_centrality`を呼び出す必要がある。** 指定された属性やレイアウトが存在しない場合はエラーを返す。サブグラフのオーバーレイ表示もサポートする。 |
| `create_ego_network` | 指定されたノードを中心としたEgo Graph（指定ホップ数以内のノード群）を新しいネットワークとして作成する。**同じ条件（中心ノード、半径）で作成されたサブグラフが既に存在する場合は、新規作成せずに既存のネットワークを再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_subgraph_from_nodes` | 指定されたノードIDのリストからサブグラフを新しいネットワークとして作成する。**ノードリストに基づいて一意な名前（`Subgraph (A,B,...)`）を生成し、同名のサブグラフが存在する場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_path_subgraph` | 指定された2ノード間の最短経路をサブグラフとして新しいネットワークとして作成する。**既存のパスサブグラフがある場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_k_core_subgraph` | K-Core（次数k以上のノード群）を抽出し、新しいネットワークとして作成する。**同じk値のK-Coreサブグラフがある場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `create_largest_component_subgraph` | 最大連結成分を抽出し、新しいネットワークとして作成する。**既に作成済みの場合は再利用する。レスポンスは辞書形式で、`network_id`を含む。** |
| `get_subgraphs` | 指定されたネットワークの子ネットワーク（サブグラフ）の一覧を取得する。 |
| `get_top_nodes` | 指定された中心性指標に基づいて、上位k個のノードを取得する。 |
| `export_network` | ネットワークをGraphML形式でエクスポートする。 |

## 3.3. MCPリソース一覧
 
MCPのリソース機能を通じて、ネットワークの生データやメタデータへの直接アクセスを提供します。
 
| Resource URI | 説明 |
|:---|:---|
| `network://{id}/metadata` | ネットワークのメタデータ（ID, 名前, 説明, 作成日時）をJSON形式で取得する。 |
| `network://{id}/graphml` | ネットワークの完全なGraphMLデータを取得する。 |
 
## 3.4. ツール定義詳細

### `update_network_metadata`
- **Description**: ネットワークの名前や説明を更新する。
- **Arguments**:
  - `network_id`: int
  - `description`: str (Optional)
  - `name`: str (Optional)

### `list_node_attributes`
- **Parameters**: `network_id`
- **Description**: Returns a list of node attributes with metadata (data type, statistics).

### `list_edge_attributes`
- **Parameters**: `network_id`
- **Description**: Returns a list of edge attributes with metadata (data type, statistics).

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

### `get_subgraphs`
- **Description**: サブグラフの一覧を取得する。
- **Arguments**:
  - `network_id`: int

### `get_top_nodes`
- **Description**: 指定された中心性指標に基づいて、上位k個のノードを取得する。
- **Arguments**:
  - `network_id`: int
  - `metric`: str ("degree", "betweenness", "closeness", "eigenvector")
  - `k`: int (default: 10)

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


**Note on Default Behavior:**
If `focus_network_id` is provided but `context_config` is omitted, the API defaults to the following configuration to ensure the focus effect is visible:
```json
"context_config": {
  "visible": true,
  "opacity": 0.1,
  "color": null // Keep original color
}
```
If you wish to show the context at full opacity, you must explicitly provide `"context_config": { "opacity": 1.0 }`.
```

**Visualization Patterns:**

The API supports three main patterns for subgraph visualization, controlled by how `network_id`, `focus_network_id`, and configurations are combined.

**Pattern 1: Global Focus (Highlight Only)**
*   **Layout**: Global (calculated on `network_id`)
*   **Metrics**: Global (calculated on `network_id`)
*   **Context**: Dimmed background
*   **Use Case**: "Show me where this subgraph is in the whole network."

```json
{
  "network_id": 12345,
  "focus_network_id": 67890,
  "node_size_config": { "attribute": "degree_centrality" }, // Global Degree
  "context_config": { "opacity": 0.1 },
  "focus_config": {} // Inherits Global Degree
}
```

**Pattern 2: Contextual Subgraph Analysis**
*   **Layout**: Global (calculated on `network_id`)
*   **Metrics**: **Subgraph** (calculated on `focus_network_id`)
*   **Context**: Dimmed background
*   **Use Case**: "Show the subgraph in context, but size nodes by their importance WITHIN the subgraph."

```json
{
  "network_id": 12345,
  "focus_network_id": 67890,
  "context_config": { "opacity": 0.1 },
  "focus_config": {
    // OVERRIDE: Use attributes from focus_network_id (67890)
    "node_size_config": {
      "attribute": "degree_centrality", // Subgraph Degree
      "min_size": 10, "max_size": 30
    }
  }
}
```

**Pattern 3: Isolated Subgraph Analysis**
*   **Layout**: **Subgraph** (calculated on `network_id` which IS the subgraph)
*   **Metrics**: **Subgraph**
*   **Context**: None
*   **Use Case**: "Extract the subgraph and optimize its layout for detailed inspection."

```json
{
  "network_id": 67890, // Subgraph IS the Main Network now
  // No focus_network_id needed
  "node_size_config": { "attribute": "degree_centrality" } // Subgraph Degree
  // Layout is calculated for 67890 directly
}
```

- **リクエストボディ例 3 (ランキングによる色分け)**

```json
{
  "network_id": 12345,
  "layout_name": "spring",
  "node_color_config": {
    "attribute": "degree_centrality",
    "scale_type": "RANKING",
    "ranking_rules": [
      { "top": 2, "color": "blue" },
      { "top": 5, "color": "green" }
    ],
    "default_color": "gray"
  }
}
```

- **リクエストボディ例 4 (サブグラフのフォーカス表示とコンテキスト設定)**

```json
{
  "network_id": 12345,
  "focus_network_id": 67890, // サブグラフID (Focus)
  "context_config": {
    "color": "#EEEEEE",        // Focus外のノード色
    "opacity": 0.1,           // Focus外の透明度
    "visible": true
  },
  "focus_config": {
    "node_color_config": {
      "static_color": "#FF0000" // Focus内のノード色 (赤)
    }
  }
}
```

- **リクエストボディ例 5 (個別のノード色指定)**

```json
{
  "network_id": 12345,
  "custom_node_colors": [
    { "node_id": "n1", "color": "red" },
    { "node_id": "n2", "color": "blue" }
  ],
  "node_size_config": { ... } // サイズは属性で指定可能
}
```

- **リクエストボディ例 6 (複合的な可視化: サイズ + フォーカス + 個別色指定)**

```json
{
  "network_id": 12345,
  "focus_network_id": 67890, // サブグラフID
  "node_size_config": {
    "attribute": "degree_centrality",
    "scale_type": "LINEAR",
    "min": 5,
    "max": 20
  },
  "context_config": {
    "color": "#D3D3D3",       // Context (サブグラフ外) はグレー
    "opacity": 0.3
  },
  "focus_config": {
    "node_color_config": {
      "static_color": "#87CEEB" // Focus (サブグラフ内) は水色
    }
  },
  "custom_node_colors": [
    { "node_id": "n1", "color": "blue" } // 特定の重要ノードだけ青 (Focus設定より優先)
  ]
}
```

- **Response Body (Success):**

```json
{
  "nodes": [
    {
      "id": "node1",
      "label": "Node 1",
      "x": 0.123,
      "y": 0.456,
      "size": 15.2,
      "color": "#ff6384"
    }
  ],
  "links": [
    {
      "source": "node1",
      "target": "node2",
      "width": 1,
      "color": "#cccccc"
    }
  ]
}
```

## 3.4. 設計思想: 動的なレンダリングデータ生成への責務集約

本システムは、LLMのFunction Calling（ツール呼び出し）機能を最大限に活用するため、アーキテクチャを大きく変更しました。

旧設計では、「計算」と「視覚ルールの永続化」をNetworkXAPIが担い、「レンダリングデータの組み立て」をBackendが担うという、責務が分散した設計でした。これは状態管理を複雑にし、LLMの動的な指示に柔軟に対応する上での足枷となっていました。

**新設計では、NetworkXAPIが「最終的なレンダリングデータを動的に生成する」という責務を一手に担います。**

LLMは、ユーザーの「次数が多いノードを大きく、コミュニティごとに色分けして」といった指示を解釈し、必要に応じて`calculate_layout`でレイアウトを計算した後、一度のツール呼び出し（`generate_visualization`）で、使用するレイアウト、ノードサイズ、ノードカラーの割り当て方法をすべて指定します。NetworkXAPIの`/tools/generate_visualization`エンドポイントは、この指示書（リクエストボディ）に基づき、最終的なJSONを返します。

このプロセスにおいて、`generate_visualization`はリクエストで指定された属性名（例: `"attribute": "degree_centrality"`）をそのまま使うわけではありません。正規化されたスキーマに基づき、以下の手順でデータを取得します。

1.  **属性名の解決**: `network_id`とリクエストされた属性名（`"degree_centrality"`）を使い、`node_attributes`テーブルを検索して、対応する`attribute_id`を特定します。
2.  **値の取得**: 解決した`attribute_id`をキーとして`node_attribute_values`テーブルを検索し、ネットワーク内の全ノードに対応する値を取得します。
3.  **レイアウトの適用**: `layout_name`が指定された場合、対応するレイアウト属性（例: `spring_layout_x`, `spring_layout_y`）をDBから取得して適用します。**計算は行いません。該当する属性が存在しない場合はエラーとなります。**

この「属性名をIDに解決する」というステップを挟むことで、データの整合性を保ち、文字列ベースの曖昧な検索を排除しています。その後、取得した値を用いてマッピング処理やスタイル計算を実行します。

この責務集約により、以下の利点が生まれます。

- **ステートレス化**: 視覚ルールを永続化しないため、データベースの状態がシンプルになります。
- **柔軟性の向上**: LLMが対話の都度、最適な視覚表現をゼロベースで考案・指示できるため、より文脈に応じたインタラクティブな分析が可能になります。
- **シンプル化**: Backendは、LLMからのツールコールをNetworkXAPIに中継し、結果をフロントエンドに流すだけの単純なプロキシとなり、システム全体のデータフローが大幅に簡潔になります。

## 3.5. REST API エンドポイント (MCP Feature Parity)

MCPツールと同等の機能をREST API経由でも利用可能にするため、以下のエンドポイントを提供します。

### `GET /api/v1/networks/{network_id}/metadata`
ネットワークのメタデータ（名前、説明など）を取得します。

**Response:**
```json
{
  "id": 1,
  "name": "Network Name",
  "description": "Network Description",
  "created_at": "...",
  "updated_at": "...",
  "is_subgraph": false,
  "parent_network_id": null
}
```

### `PUT /api/v1/networks/{network_id}/metadata`
ネットワークのメタデータを更新します。

**Request:**
```json
{
  "name": "New Name",
  "description": "New Description"
}
```

**Response:** 更新後のメタデータ（GETと同じ形式）

