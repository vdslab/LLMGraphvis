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
| `POST` | `/tools/initialize_network` | GraphMLデータを受け取り、1.正規化、2.DBへのノード/エッジ保存、3.初期レイアウト(Spring)計算とDB保存、4.デフォルトスタイルを適用した初期レンダリングデータの生成、までを一貫して実行する。 |
| `GET` | `/tools/list_attributes` | ネットワークに存在する属性（計算済みまたは元から存在）の一覧を返す。 |
| `POST` | `/tools/calculate_centrality` | 中心性指標を計算して永続化する。具体的には、まず属性の**定義**（例: 'degree_centrality'）が`node_attributes`に存在するか確認し、なければ`network_id`に紐付けて作成する。次に、各ノードの計算**値**を、定義のIDを参照して`node_attribute_values`に保存する。 |
| `POST` | `/tools/calculate_layout` | レイアウト座標を計算して永続化する。`layout_name`（例: 'circular'）を受け取り、`{layout_name}_x`, `{layout_name}_y` という属性として保存する。 |
| `POST` | `/tools/generate_visualization` | レイアウト、ノードサイズ、ノードカラー等の視覚的割り当てに関するすべてのパラメータを受け取り、最終的なレンダリングデータを動的に生成して返す。**レイアウト計算は行わず、計算済みの座標データを使用する。** |

## 3.3. API詳細

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
  "message": "Degree centrality calculated and saved as 'degree_centrality' attribute."
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

LLMは、ユーザーの「次数が多いノードを大きく、コミュニティごとに色分けして」といった指示を解釈し、一度のツール呼び出しで、レイアウト、ノードサイズ、ノードカラーの割り当て方法をすべて指定します。NetworkXAPIの`/tools/generate_visualization`エンドポイントは、この指示書（リクエストボディ）に基づき、最終的なJSONを返します。

このプロセスにおいて、`generate_visualization`はリクエストで指定された属性名（例: `"attribute": "degree_centrality"`）をそのまま使うわけではありません。正規化されたスキーマに基づき、以下の手順でデータを取得します。

1.  **属性名の解決**: `network_id`とリクエストされた属性名（`"degree_centrality"`）を使い、`node_attributes`テーブルを検索して、対応する`attribute_id`を特定します。
2.  **値の取得**: 解決した`attribute_id`をキーとして`node_attribute_values`テーブルを検索し、ネットワーク内の全ノードに対応する値を取得します。
3.  **レイアウトの適用**: `layout_name`が指定された場合、対応するレイアウト属性（例: `spring_layout_x`, `spring_layout_y`）をDBから取得して適用します。**計算は行いません。**

この「属性名をIDに解決する」というステップを挟むことで、データの整合性を保ち、文字列ベースの曖昧な検索を排除しています。その後、取得した値を用いてマッピング処理やスタイル計算を実行します。

この責務集約により、以下の利点が生まれます。

- **ステートレス化**: 視覚ルールを永続化しないため、データベースの状態がシンプルになります。
- **柔軟性の向上**: LLMが対話の都度、最適な視覚表現をゼロベースで考案・指示できるため、より文脈に応じたインタラクティブな分析が可能になります。
- **シンプル化**: Backendは、LLMからのツールコールをNetworkXAPIに中継し、結果をフロントエンドに流すだけの単純なプロキシとなり、システム全体のデータフローが大幅に簡潔になります。
