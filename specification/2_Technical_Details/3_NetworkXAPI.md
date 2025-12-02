# 3. ネットワーク計算サービス仕様 (NetworkXAPI)

**前提知識レベル:**
- マイクロサービスの概念
- NetworkXライブラリに関する知識
- FastAPIに関する開発経験

NetworkXAPIは、ネットワークに関する計算処理と、その結果の永続化に特化したREST APIサービスです。計算結果などの状態はすべて外部のデータベースに永続化するため、サービス自体は**ステートレス**に設計されており、水平スケールが可能です。

## 3.1. 役割

- `API`サービスからCPU負荷の高い計算処理をオフロードする。
- **データベースに直接接続**し、計算結果（レイアウト座標、中心性指標など）を、ネットワークの**永続的な属性として**型別に分離されたテーブル（`node_float_attribute_values`など）に永続化する。
- 属性が未計算の場合のみ`NetworkX`ライブラリを利用して計算を実行する。
- LLMが定義した動的なリクエストに基づき、属性計算、レイアウト計算、視覚マッピングを一度に実行し、**最終的なレンダリングデータを生成して返す**。
- 様々な形式のGraphMLファイルをシステムで一貫して扱える標準形式に変換・正規化する。

## 3.2. APIエンドポイント一覧

`API`サービスから内部的に呼び出される、主要なツールエンドポイントです。

| Method | Path | 説明 |
|:---|:---|:---|
| `POST` | `/tools/initialize_network` | GraphMLデータを受け取り、1.正規化（属性型の推論と`data_type`の保存を含む）、2.DBへのノード/エッジ保存（値は型別のテーブルへ）、3.初期レイアウト(Spring)計算とDB保存、4.デフォルトスタイルを適用した初期レンダリングデータの生成、までを一貫して実行する。 |
| `GET` | `/tools/list_node_attributes` | ネットワークに存在するノード属性（計算済みまたは元から存在）の一覧を返す。 |
| `GET` | `/tools/list_edge_attributes` | ネットワークに存在するエッジ属性（計算済みまたは元から存在）の一覧を返す。 |
| `POST` | `/tools/calculate_centrality` | 中心性指標を計算して永続化する。具体的には、まず属性の**定義**（例: 'degree_centrality'）が`node_attributes`に存在するか確認し、なければ`network_id`に紐付けて作成する。次に、各ノードの計算**値**を、定義のIDを参照して`node_attribute_values`に保存する。レスポンスは計算完了のステータスのみを返す。 |
| `POST` | `/tools/calculate_layout` | レイアウト座標を計算して永続化する。`layout_name`（例: 'circular'）を受け取り、`{layout_name}_x`, `{layout_name}_y` という属性として保存する。レスポンスは計算完了のステータスのみを返す。 |
| `POST` | `/tools/generate_visualization` | レイアウト、ノードサイズ、ノードカラー等の視覚的割り当てに関するすべてのパラメータを受け取り、最終的なレンダリングデータを動的に生成して返す。**レイアウト計算は行わず、計算済みの座標データを使用する。新しいレイアウトを適用する場合は、事前に`/tools/calculate_layout`を呼び出す必要がある。** サブグラフのオーバーレイ表示もサポートする。 |
| `POST` | `/tools/create_ego_network` | 指定されたノードを中心としたEgo Graph（指定ホップ数以内のノード群）を新しいネットワークとして作成する。 |
| `POST` | `/tools/create_subgraph_from_nodes` | 指定されたノードIDのリストからサブグラフを新しいネットワークとして作成する。 |
| `POST` | `/tools/create_path_subgraph` | 指定された2ノード間の最短経路をサブグラフとして新しいネットワークとして作成する。 |
| `POST` | `/tools/create_k_core_subgraph` | K-Core（次数k以上のノード群）を抽出し、新しいネットワークとして作成する。 |
| `POST` | `/tools/create_largest_component_subgraph` | 最大連結成分を抽出し、新しいネットワークとして作成する。 |
| `GET` | `/tools/get_subgraphs` | 指定されたネットワークの子ネットワーク（サブグラフ）の一覧を取得する。 |
| `POST` | `/tools/get_top_nodes` | 指定された中心性指標に基づいて、上位k個のノードを取得する。 |

## 3.3. API詳細

### 1. 属性一覧取得 (Node)
- **Endpoint**: `GET /tools/list_node_attributes`
- **Description**: ネットワーク内の利用可能なノード属性一覧を取得する。
- **Parameters**:
  - `network_id` (query): ネットワークID
- **Response**:
  - `attributes`: List[str] - 属性名のリスト

### 2. 属性一覧取得 (Edge)
- **Endpoint**: `GET /tools/list_edge_attributes`
- **Description**: ネットワーク内の利用可能なエッジ属性一覧を取得する。
- **Parameters**:
  - `network_id` (query): ネットワークID
- **Response**:
  - `attributes`: List[str] - 属性名のリスト

### 3. 中心性計算
- **Endpoint**: `POST /tools/calculate_centrality`
- **Description**: 指定された中心性指標を計算し、ノード属性として保存する。
- **Request Body**:
  - `network_id`: int
  - `centrality_type`: str ("degree", "betweenness", "closeness", "eigenvector")
- **Response**:
  - `status`: str ("success")
  - `message`: str

### 4. レイアウト計算
- **Endpoint**: `POST /tools/calculate_layout`
- **Description**: 指定されたレイアウトアルゴリズムで座標を計算し、ノード属性として保存する。
- **Request Body**:
  - `network_id`: int
  - `layout_name`: str ("spring", "circular", "kamada_kawai", "shell", "spectral")
- **Response**:
  - `status`: str ("success")
  - `message`: str

### 5. サブグラフ作成 (Ego Network)
- **Endpoint**: `POST /tools/create_ego_network`
- **Description**: 指定ノードを中心としたEgo Graphを作成する。
- **Request Body**:
  - `source_network_id`: int
  - `center_node_id`: str
  - `radius`: int
- **Response**:
  - `new_network_id`: int
  - `name`: str

### 6. サブグラフ作成 (From Nodes)
- **Endpoint**: `POST /tools/create_subgraph_from_nodes`
- **Description**: ノードIDリストからサブグラフを作成する。
- **Request Body**:
  - `source_network_id`: int
  - `node_ids`: List[str]
- **Response**:
  - `new_network_id`: int
  - `name`: str

### 7. サブグラフ作成 (Path)
- **Endpoint**: `POST /tools/create_path_subgraph`
- **Description**: 最短経路のサブグラフを作成する。
- **Request Body**:
  - `source_network_id`: int
  - `source_node_id`: str
  - `target_node_id`: str
- **Response**:
  - `new_network_id`: int
  - `name`: str

### 8. サブグラフ作成 (K-Core)
- **Endpoint**: `POST /tools/create_k_core_subgraph`
- **Description**: K-Coreサブグラフを作成する。
- **Request Body**:
  - `source_network_id`: int
  - `k`: int
- **Response**:
  - `new_network_id`: int
  - `name`: str

### 9. サブグラフ作成 (Largest Component)
- **Endpoint**: `POST /tools/create_largest_component_subgraph`
- **Description**: 最大連結成分のサブグラフを作成する。
- **Request Body**:
  - `source_network_id`: int
- **Response**:
  - `new_network_id`: int
  - `name`: str

### 10. サブグラフ一覧取得
- **Endpoint**: `GET /tools/get_subgraphs`
- **Description**: サブグラフの一覧を取得する。
- **Parameters**:
  - `network_id` (query): 親ネットワークID
- **Response**:
  - `subgraphs`: List[{ "id": int, "name": str, "created_at": str }]

### 11. 重要ノード取得
- **Endpoint**: `POST /tools/get_top_nodes`
- **Description**: 指定された中心性指標に基づいて、上位k個のノードを取得する。
- **Request Body**:
  - `network_id`: int
  - `metric`: str ("degree", "betweenness", "closeness", "eigenvector")
  - `k`: int (default: 10)
- **Response**:
  - `top_nodes`: List[{ "node_id": str, "score": float }]

### `/tools/calculate_centrality`

- **Request Body:**

```json
{
  "network_id": 12345,
  "centrality_type": "degree"
}
```

- **Response Body (Success):**

```json
{
  "status": "success",
  "message": "degree centrality calculated."
}
```

### `/tools/calculate_layout`

- **Request Body:**

```json
{
  "network_id": 12345,
  "layout_name": "circular"
}
```

- **Response Body (Success):**

```json
{
  "status": "success",
  "message": "Layout 'circular' calculated and saved."
}
```

### `/tools/generate_visualization`

- **リクエストボディ例 1 (次数中心性でサイズ、コミュニティで色分け)**

```json
{
  "network_id": 12345,
  "layout_name": "spring",
  "node_size_config": {
    "attribute": "degree_centrality",
    "scale_type": "LINEAR",
    "min_size": 3,
    "max_size": 25
  },
  "node_color_config": {
    "attribute": "community_id",
    "scale_type": "CATEGORICAL",
    "color_map": {
      "0": "#ff6384",
      "1": "#36a2eb",
      "2": "#ffce56"
    }
  }
}
```

- **リクエストボディ例 2 (媒介中心性で色分け)**

```json
{
  "network_id": 12345,
  "layout_name": "kamada_kawai",
  "node_color_config": {
    "attribute": "betweenness_centrality",
    "scale_type": "LINEAR",
    "gradient": ["#d1e0ff", "#003399"]
  }
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

- **リクエストボディ例 4 (サブグラフのオーバーレイ表示と色設定)**

```json
{
  "network_id": 12345,
  "overlay_network_id": 67890, // サブグラフID
  "overlay_config": {
    "highlight_color": "#FF0000", // サブグラフに含まれるノード・エッジの色
    "dimmed_color": "#EEEEEE"      // それ以外のノード・エッジの色
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

- **リクエストボディ例 6 (複合的な可視化: サイズ + オーバーレイ + 個別色指定)**

```json
{
  "network_id": 12345,
  "overlay_network_id": 67890, // サブグラフID
  "node_size_config": {
    "attribute": "degree_centrality",
    "scale_type": "LINEAR",
    "min": 5,
    "max": 20
  },
  "overlay_config": {
    "highlight_color": "#87CEEB", // サブグラフ内は水色
    "dimmed_color": "#D3D3D3"     // サブグラフ外はグレー
  },
  "custom_node_colors": [
    { "node_id": "n1", "color": "blue" } // 特定の重要ノードだけ青 (オーバーレイ設定より優先)
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
3.  **レイアウトの適用**: `layout_name`が指定された場合、対応するレイアウト属性（例: `spring_layout_x`, `spring_layout_y`）をDBから取得して適用します。**計算は行いません。**

この「属性名をIDに解決する」というステップを挟むことで、データの整合性を保ち、文字列ベースの曖昧な検索を排除しています。その後、取得した値を用いてマッピング処理やスタイル計算を実行します。

この責務集約により、以下の利点が生まれます。

- **ステートレス化**: 視覚ルールを永続化しないため、データベースの状態がシンプルになります。
- **柔軟性の向上**: LLMが対話の都度、最適な視覚表現をゼロベースで考案・指示できるため、より文脈に応じたインタラクティブな分析が可能になります。
- **シンプル化**: Backendは、LLMからのツールコールをNetworkXAPIに中継し、結果をフロントエンドに流すだけの単純なプロキシとなり、システム全体のデータフローが大幅に簡潔になります。
