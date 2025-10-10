# NetworkX MCP Server - 新機能ガイド

## 概要

NetworkX MCPサーバーに以下の新機能を追加しました：

1. **グラフキャッシュ機能**: 計算済みのグラフをメモリ上に保持
2. **拡張された指標計算**: 中心性以外の指標（コミュニティ検出、クラスタリング係数など）
3. **計算と表示の分離**: 2段階プロセスによる高速な可視化切り替え

## アーキテクチャの変更

### 従来のステートレス方式
```
GraphML → パース → 計算 → 結果を返す
（毎回GraphMLをパースして計算）
```

### 新しいステートフル方式
```
【第1段階：計算】
GraphML → パース → レイアウト計算 → 全指標計算 → キャッシュに保存 → graph_id返却

【第2段階：表示】
graph_id + 指標名 → キャッシュから取得 → 可視化データ生成 → 返却
（計算済みデータを使用するため高速）
```

## 新しいエンドポイント

### 1. `/tools/calculate_and_store_metrics` (POST)

GraphMLを受け取り、レイアウトと全指標を計算してキャッシュに保存します。

**リクエスト:**
```json
{
  "graphml_content": "<graphml>...</graphml>",
  "layout_type": "spring",
  "layout_params": {},
  "metrics_to_calculate": null
}
```

**パラメータ:**
- `graphml_content` (必須): GraphML文字列
- `layout_type` (オプション): レイアウトアルゴリズム（デフォルト: "spring"）
- `layout_params` (オプション): レイアウトパラメータ
- `metrics_to_calculate` (オプション): 計算する指標のリスト（nullの場合は全て計算）

**レスポンス:**
```json
{
  "result": {
    "success": true,
    "graph_id": "uuid-string",
    "metadata": {
      "layout_type": "spring",
      "calculated_metrics": ["degree_centrality", "clustering", "community_louvain", ...],
      "num_nodes": 25,
      "num_edges": 45,
      "is_directed": false
    },
    "message": "Successfully calculated and stored 9 metrics"
  }
}
```

### 2. `/tools/get_visualization_data` (POST)

キャッシュされたグラフから指定された指標に基づく可視化データを取得します。

**リクエスト:**
```json
{
  "graph_id": "uuid-string",
  "metric_name": "degree_centrality",
  "color_scheme": "viridis",
  "size_range": [10, 50]
}
```

**パラメータ:**
- `graph_id` (必須): グラフのID
- `metric_name` (必須): 可視化する指標名
- `color_scheme` (オプション): カラースキーム（viridis, plasma, inferno）
- `size_range` (オプション): ノードサイズの範囲 [min, max]

**レスポンス:**
```json
{
  "result": {
    "success": true,
    "graph_id": "uuid-string",
    "metric_name": "degree_centrality",
    "elements": {
      "nodes": [
        {
          "data": {"id": "0", "label": "Node 0", "degree_centrality": 0.5},
          "position": {"x": 250, "y": 300},
          "style": {"background-color": "rgb(68, 1, 84)", "width": 30, "height": 30}
        },
        ...
      ],
      "edges": [
        {"data": {"source": "0", "target": "1"}},
        ...
      ]
    },
    "metadata": {
      "num_nodes": 25,
      "num_edges": 45,
      "metric_type": "continuous",
      "value_range": {"min": 0.0, "max": 1.0}
    }
  }
}
```

### 3. `/tools/get_available_metrics` (POST)

キャッシュされたグラフで利用可能な指標のリストを取得します。

**リクエスト:**
```json
{
  "graph_id": "uuid-string"
}
```

**レスポンス:**
```json
{
  "result": {
    "success": true,
    "graph_id": "uuid-string",
    "available_metrics": [
      "clustering",
      "community_louvain",
      "core_number",
      "triangles",
      "degree_centrality",
      "closeness_centrality",
      "betweenness_centrality",
      "eigenvector_centrality",
      "pagerank"
    ],
    "graph_info": {
      "num_nodes": 25,
      "num_edges": 45,
      "layout_type": "spring",
      "is_directed": false
    }
  }
}
```

### 4. `/cache/stats` (GET)

キャッシュの統計情報を取得します。

**レスポンス:**
```json
{
  "success": true,
  "stats": {
    "size": 1,
    "max_size": 100,
    "ttl_minutes": 60,
    "graph_ids": ["uuid-string"]
  }
}
```

## 利用可能な指標

### 中心性指標
- `degree_centrality`: 次数中心性
- `closeness_centrality`: 近接中心性
- `betweenness_centrality`: 媒介中心性
- `eigenvector_centrality`: 固有ベクトル中心性
- `pagerank`: PageRank

### ネットワーク指標
- `clustering`: クラスタリング係数
- `core_number`: k-coreのコア番号
- `triangles`: 三角形の数
- `eccentricity`: 離心率（連結グラフのみ）

### コミュニティ検出
- `community_louvain`: Louvain法によるコミュニティ検出
- `community_label_propagation`: ラベル伝播法
- `community_greedy_modularity`: 貪欲モジュラリティ最適化

## 使用例

### Python

```python
import requests

BASE_URL = "http://localhost:8001"

# 1. サンプルネットワークを取得
response = requests.get(f"{BASE_URL}/get_sample_network")
graphml_content = response.json()["graphml_content"]

# 2. 指標を計算してキャッシュに保存
payload = {
    "graphml_content": graphml_content,
    "layout_type": "spring",
    "layout_params": {},
    "metrics_to_calculate": None  # 全ての指標を計算
}
response = requests.post(f"{BASE_URL}/tools/calculate_and_store_metrics", json=payload)
graph_id = response.json()["result"]["graph_id"]

# 3. 利用可能な指標を確認
payload = {"graph_id": graph_id}
response = requests.post(f"{BASE_URL}/tools/get_available_metrics", json=payload)
metrics = response.json()["result"]["available_metrics"]
print(f"Available metrics: {metrics}")

# 4. 次数中心性で可視化データを取得
payload = {
    "graph_id": graph_id,
    "metric_name": "degree_centrality",
    "color_scheme": "viridis",
    "size_range": [10, 50]
}
response = requests.post(f"{BASE_URL}/tools/get_visualization_data", json=payload)
viz_data = response.json()["result"]

# 5. コミュニティ検出で可視化データを取得
payload = {
    "graph_id": graph_id,
    "metric_name": "community_louvain",
    "color_scheme": "viridis"
}
response = requests.post(f"{BASE_URL}/tools/get_visualization_data", json=payload)
community_viz_data = response.json()["result"]
```

### cURL

```bash
# 1. サンプルネットワークを取得
curl http://localhost:8001/get_sample_network > sample.json

# 2. 指標を計算してキャッシュに保存
curl -X POST http://localhost:8001/tools/calculate_and_store_metrics \
  -H "Content-Type: application/json" \
  -d '{
    "graphml_content": "...",
    "layout_type": "spring",
    "layout_params": {},
    "metrics_to_calculate": null
  }'

# 3. 可視化データを取得
curl -X POST http://localhost:8001/tools/get_visualization_data \
  -H "Content-Type: application/json" \
  -d '{
    "graph_id": "uuid-string",
    "metric_name": "degree_centrality",
    "color_scheme": "viridis",
    "size_range": [10, 50]
  }'
```

## テスト

テストスクリプトを実行して動作確認できます：

```bash
# サーバーを起動
cd NetworkXMCP
python main.py

# 別のターミナルでテストを実行
python test_new_features.py
```

## キャッシュの設定

グラフキャッシュは以下のデフォルト設定で動作します：

- **最大サイズ**: 100グラフ
- **有効期限（TTL）**: 60分
- **削除方式**: LRU（Least Recently Used）

これらの設定は `NetworkXMCP/tools/graph_cache.py` の `GraphCache` クラスで変更できます。

## パフォーマンスの改善

新しいアーキテクチャにより、以下のパフォーマンス改善が期待できます：

1. **初回計算**: 全指標を一度に計算（約1-2秒）
2. **表示切り替え**: キャッシュから取得（約0.1秒以下）
3. **メモリ効率**: LRU方式により古いデータを自動削除

## 注意事項

- グラフIDは60分後に期限切れになります
- キャッシュは最大100グラフまで保持します
- サーバーを再起動するとキャッシュはクリアされます

## トラブルシューティング

### グラフIDが見つからない

```json
{
  "success": false,
  "error": "Graph not found in cache: uuid-string"
}
```

**原因**: グラフIDが期限切れまたは存在しない

**解決策**: `calculate_and_store_metrics` を再度実行して新しいグラフIDを取得

### 指標が見つからない

```json
{
  "success": false,
  "error": "Metric 'xxx' not found. Available metrics: [...]"
}
```

**原因**: 指定した指標が計算されていない

**解決策**: `get_available_metrics` で利用可能な指標を確認

## まとめ

新機能により、以下が可能になりました：

✅ 計算と表示の分離による高速な可視化切り替え
✅ 中心性以外の多様な指標の可視化
✅ コミュニティ検出による構造分析
✅ メモリ効率的なキャッシュ管理

これにより、より柔軟で高速なネットワーク分析が可能になりました。
