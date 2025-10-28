# 4. データベーススキーマ仕様

このドキュメントでは、LLMGraph-visアプリケーションで使用される主要なデータベーススキーマを定義します。

## 4.1. 計算結果キャッシュ (`calculation_results`)

NetworkX等で計算された中心性指標などの分析結果を永続化するためのテーブルです。高コストな計算の再実行を防ぐことを目的とします。

### 基本設計方針

- **ハイブリッドモデル**: 柔軟性とパフォーマンスを両立するため、メタデータをリレーショナルカラムで、変動しやすい計算結果を`JSONB`カラムで管理するハイブリッドアプローチを採用します。
- **データ型**: 検索性能と柔軟性に優れた `JSONB` 型を計算結果の格納に使用します。
- **インデックス**: `JSONB` カラムには `GIN` インデックスを作成し、高速な検索を可能にします。

### 推奨スキーマ

```sql
CREATE TABLE calculation_results (
    id SERIAL PRIMARY KEY,
    graph_id INT NOT NULL,          -- 外部キーとしてグラフテーブルに関連付け
    datatype TEXT NOT NULL,         -- 'degree_centrality', 'pagerank', 'betweenness_centrality', 'closeness_centrality', 'eigenvector_centrality', 'load_centrality', 'edge_betweenness_centrality', 'clustering', 'transitivity', 'modularity' などの指標名
    data JSONB NOT NULL,            -- 計算結果の本体
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(graph_id, datatype)
);

-- 高速な検索のためのGINインデックス
CREATE INDEX idx_gin_calculation_data ON calculation_results USING GIN (data);
```

### `data` カラムのJSONB構造

計算結果は、分析クエリの効率を最大化するため、以下の「オブジェクトの配列」形式で格納します。

- **キーの短縮**: ストレージ効率のため、キーは `"n"` (node) と `"s"` (score) に短縮します。
- **形式**: `[{"n": "node_id", "s": score}, ...]`

#### JSONBデータ格納例

`degree_centrality` の計算結果を格納する場合の例です。

```json
[
  {
    "n": "node_1",
    "s": 0.24
  },
  {
    "n": "node_2",
    "s": 0.16
  },
  {
    "n": "node_3",
    "s": 0.31
  }
]
```

この構造により、スコア (`s`) に基づくフィルタリング、ソート、集計が効率的に行えます。

### 運用上の注意

- **指標の区別**: `degree_centrality`（正規化された値）と`degree`（次数の生カウント）のように、異なる指標は `datatype` フィールドで明確に区別してください。
- **有向グラフ**: 入次数と出次数を別々に保存する場合は、`datatype` を `in_degree_centrality` と `out_degree_centrality` のように分けてください。
- **アトミックな更新**: 既存の計算結果を更新する場合は、`ON CONFLICT (graph_id, datatype) DO UPDATE` を使用してアトミックに上書きします。
