# 3. ネットワーク計算サービス仕様 (NetworkXMCP)

**前提知識レベル:**
- マイクロサービスの概念
- NetworkXライブラリに関する知識
- FastAPIに関する開発経験

NetworkXMCPは、ネットワークに関する計算処理と、その結果の永続化に特化した**ステートフル**なマイクロサービスです。

## 3.1. 役割

- `API`サービスからCPU負荷の高い計算処理をオフロードする。
- **データベースに直接接続**し、計算結果（レイアウト座標、中心性指標など）をネットワークの**永続的な属性として**永続化する。
- 属性が未計算の場合のみ`NetworkX`ライブラリを利用して計算を実行する。
- 視覚マッピングルールを`visual_mapping_rules`テーブルに永続化する。
- 様々な形式のGraphMLファイルをシステムで一貫して扱える標準形式に変換・正規化する。

## 3.2. APIエンドポイント一覧

`API`サービスから内部的に呼び出される、主要なツールエンドポイントです。

| Method | Path | 説明 |
|:---|:---|:---|
| `GET` | `/health` | サービスのヘルスチェックを行う。 |
| `GET` | `/tools/list_attributes` | ネットワークに存在する属性（計算済みまたは元から存在）の一覧を返す。 |
| `POST` | `/tools/calculate_centrality` | 中心性指標を**計算**し、その結果の**値**を`attribute_values`系のテーブルに、**定義**を`attributes`系のテーブルに保存する。 |
| `POST` | `/tools/apply_metric_to_visual` | 指定された指標を視覚プロパティにマッピングするルールを`visual_mapping_rules`テーブルに保存（作成または更新）する。 |
| `POST` | `/tools/change_layout` | ネットワークレイアウトを計算し、ノードの座標の**値**を`attribute_values`系のテーブルに、**定義**を`attributes`系のテーブルに保存する。GraphMLアップロード時の初期レイアウト計算にも使用される。 |
| `POST` | `/tools/highlight_nodes` | 指定された条件に合うノードをハイライトするためのマッピングルールを`visual_mapping_rules`テーブルに保存する。 |
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

### `/tools/apply_metric_to_visual`

- **Request Body:**

```json
{
  "network_id": "net_12345",
  "attribute_name": "degree_centrality",
  "visual_property": "NODE_SIZE",
  "mapping_options": {
    "scale_type": "LINEAR",
    "output_min_float": 1.0,
    "output_max_float": 20.0
  }
}
```

- **Response Body (Success):**

```json
{
  "status": "success",
  "message": "Visual mapping rule for NODE_SIZE has been created or updated."
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

## 3.4. 設計思想: 計算と可視化の分離

本システムは、LLMの複数ツール呼び出し機能を活用し、「計算」と「可視化」の責務を明確に分離しています。NetworkXMCPはネットワークの**計算**と、その結果である**属性や視覚ルールの永続化**に責務を持ちます。一方、Backendサービスが、永続化されたデータから最終的な**レンダリングデータを組み立てる**責務を担います。この分離により、ユーザーは「次数中心性を計算して」といった分析の指示と、「その結果をノードの大きさで表現して」といった可視化の指示を、自然な対話の中で組み合わせることができます。
