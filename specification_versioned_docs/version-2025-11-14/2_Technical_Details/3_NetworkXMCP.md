# 3. ネットワーク計算サービス仕様 (NetworkXMCP)

**前提知識レベル:**
- マイクロサービスの概念
- NetworkXライブラリに関する知識
- FastAPIに関する開発経験

NetworkXMCPは、ネットワークに関する計算処理と、その結果の永続化に特化した**ステートフル**なマイクロサービスです。

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
| `GET` | `/health` | サービスのヘルスチェックを行う。 |
| `GET` | `/tools/list_attributes` | ネットワークに存在する属性（計算済みまたは元から存在）の一覧を返す。 |
| `POST` | `/tools/calculate_centrality` | 中心性指標を**計算**し、その結果の**値**を`node_float_attribute_values`等のテーブルに、**定義**を`node_attributes`等のテーブルに保存する。 |
| `POST` | `/tools/change_layout` | ネットワークレイアウトを計算し、ノードの座標の**値**を`node_float_attribute_values`等のテーブルに、**定義**を`node_attributes`等のテーブルに保存する。GraphMLアップロード時の初期レイアウト計算にも使用される。 |
| `POST` | `/tools/generate_visualization` | **【新設】**レイアウト、ノードサイズ、ノードカラー等の視覚的割り当てに関するすべてのパラメータを受け取り、最終的なレンダリングデータを動的に生成して返す。 |
| `POST` | `/tools/convert_graphml` | アップロードされたGraphMLファイルを解析・修正し、正規化されたGraphMLを返す。（ステートレス）<br/>正規化には、属性名の標準化、特定のデータ型への変換、欠損値の処理、およびシステムで一貫して扱えるGraphML形式への変換が含まれます。 |

## 3.3. API詳細

### `/tools/calculate_centrality`

- **Request Body:**

```json
{
  "network_id": "net_12345",
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

### `/tools/generate_visualization`

- **Request Body:**

```json
{
  "network_id": "net_12345",
  "layout_config": {
    "name": "spring",
    "params": { "k": 0.1 }
  },
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

### `/tools/change_layout`

- **Request Body:**

```json
{
  "network_id": "net_12345",
  "layout_name": "spring"
}
```

- **Response Body (Success):**

```json
{
  "status": "success",
  "message": "Layout calculated and node positions saved as attributes."
}
```

## 3.4. 設計思想: 動的なレンダリングデータ生成への責務集約

本システムは、LLMのFunction Calling（ツール呼び出し）機能を最大限に活用するため、アーキテクチャを大きく変更しました。

旧設計では、「計算」と「視覚ルールの永続化」をNetworkXMCPが担い、「レンダリングデータの組み立て」をBackendが担うという、責務が分散した設計でした。これは状態管理を複雑にし、LLMの動的な指示に柔軟に対応する上での足枷となっていました。

**新設計では、NetworkXMCPが「最終的なレンダリングデータを動的に生成する」という責務を一手に担います。**

LLMは、ユーザーの「次数が多いノードを大きく、コミュニティごとに色分けして」といった指示を解釈し、一度のツール呼び出しで、レイアウト、ノードサイズ、ノードカラーの割り当て方法をすべて指定します。NetworkXMCPの`/tools/generate_visualization`エンドポイントは、この指示書（リクエストボディ）に基づき、必要な属性計算（キャッシュがあれば利用）、マッピング処理、スタイル計算をすべて実行し、フロントエンドが直接描画できる最終的なJSONを返します。

この責務集約により、以下の利点が生まれます。

- **ステートレス化**: 視覚ルールを永続化しないため、データベースの状態がシンプルになります。
- **柔軟性の向上**: LLMが対話の都度、最適な視覚表現をゼロベースで考案・指示できるため、より文脈に応じたインタラクティブな分析が可能になります。
- **シンプル化**: Backendは、LLMからのツールコールをNetworkXMCPに中継し、結果をフロントエンドに流すだけの単純なプロキシとなり、システム全体のデータフローが大幅に簡潔になります。
