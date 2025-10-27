## Degree（次数）中心性の格納フォーマット

このドキュメントでは、グラフ解析の出力（ここでは degree 中心性の計算結果）をデータベースに保存する際の推奨フォーマットを示します。保存形式は後続の解析や可視化で再利用しやすい構造にします。

### 目的の要約

- ノードごとの degree 値を保存しておき、後で可視化やフィルタリング、統計に利用できるようにする。
- 計算の発生源（どのグラフ、どの手法、いつ計算したか）を明確にする。

### 推奨スキーマ（SQL 例）

```sql
CREATE TABLE degree_centrality (
  id BIGSERIAL PRIMARY KEY,
  graph_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  degree INTEGER NOT NULL,
  normalized_degree DOUBLE PRECISION, -- 必要なら正規化値
  method TEXT NOT NULL DEFAULT 'degree',
  metadata JSONB,                     -- オプション: 計算パラメータなど
  computed_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE(graph_id, node_id, method)
);

-- 検索を速くするための索引
CREATE INDEX idx_degree_graph ON degree_centrality(graph_id);
CREATE INDEX idx_degree_node ON degree_centrality(node_id);
```

### JSON ドキュメント形式（APIやNoSQL保存向け）

1 レコードの例:

```json
{
  "graph_id": "G1",
  "node_id": "n1",
  "degree": 12,
  "normalized_degree": 0.24,
  "method": "degree",
  "metadata": { "note": "undirected simple graph", "edge_count": 240 },
  "computed_at": "2025-10-27T12:34:56Z"
}
```

バルク挿入の例（配列）:

```json
[
  {
    "graph_id": "G1",
    "node_id": "n1",
    "degree": 12,
    "normalized_degree": 0.24,
    "method": "degree"
  },
  {
    "graph_id": "G1",
    "node_id": "n2",
    "degree": 8,
    "normalized_degree": 0.16,
    "method": "degree"
  }
]
```

### 正規化方法の例

- 正規化は文脈に依存します。代表例:
  - divide by (n-1): normalized = degree / (N-1)
  - min-max: (degree - minDegree) / (maxDegree - minDegree)

保存時にはどの正規化を使ったかを `metadata` または別カラム `normalization` に格納してください。

### 運用上の注意とエッジケース

- マルチグラフや有向グラフの場合、`degree` の定義を明確にする（入次数/出次数/無向での合算など）。`metadata` に `directed: true` や `count_method: "in|out|both"` を入れるとよい。
- 局所的に頻繁に再計算される場合は、一意キー (graph_id,node_id,method) を上書きする戦略を採る。
- 大規模グラフではバルクインサートとバッチ処理で書き込みを行い、必要ならタイムスタンプでバージョン管理を行う。

### 利用例（フロントでの使い方）

- フロントがノードの色・サイズを degree によって決めたい場合、描画 API に入れる前に degree_centrality テーブルから最新の degree 値を取得し、ノードの `style.size` や `style.color` を決定するためのルールに変換して `rendering-data` を生成します。

---

このフォーマットは軽量かつ再利用しやすいことを優先しています。別の中心性（PageRank, betweenness 等）を追加する場合は `method` を拡張し、必要なら `metric_name` として保存してください。
