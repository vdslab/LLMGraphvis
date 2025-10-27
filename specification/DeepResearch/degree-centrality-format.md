## 次数中心性 (Degree Centrality) の格納フォーマット

このドキュメントでは、グラフの次数中心性の計算結果をデータベースに保存する際の推奨フォーマットを、[DB設計指針](./database.md)に基づき具体的に示します。

### 基本方針

- **データ型**: `jsonb` を使用します。
- **構造**: ノードとスコアのペアを「オブジェクトの配列」として格納します。
- **メタデータ**: 計算の発生源（どのグラフ、どの手法か）をリレーショナルカラムで明確にします。

### 推奨スキーマ (`centrality_results` テーブル)

[DB設計指針](./database.md)で推奨されている `centrality_results` テーブルを基本とします。

```sql
CREATE TABLE centrality_results (
    id SERIAL PRIMARY KEY,
    graph_id INT NOT NULL,          -- 外部キーとしてグラフテーブルに関連付け
    datatype TEXT NOT NULL,         -- 'degree_centrality', 'pagerank' などの指標名
    data JSONB NOT NULL,            -- 計算結果の本体
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(graph_id, datatype)
);

-- 高速な検索のためのGINインデックス
CREATE INDEX idx_gin_centrality_data ON centrality_results USING GIN (data);
```

### `data` カラムの具体的なJSONB構造

次数中心性の計算結果（NetworkXの `degree_centrality()` の出力など）は、以下のJSON構造に変換して `data` カラムに格納します。

- **キーの短縮**: ストレージ効率のため、キーは `"n"` (node) と `"s"` (score) に短縮します。
- **形式**: `[{"n": "node_id", "s": score}, ...]`

**JSONBデータ格納例:**

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

この構造により、[DB設計指針](./database.md)で示されているように、スコア (`s`) に基づくフィルタリングやソートが効率的に行えます。

### 運用上の注意

- **正規化**: `degree_centrality` のように正規化された値か、単なる `degree`（次数の生カウント）かは `datatype` フィールドで明確に区別してください。（例: `datatype = 'degree'` vs `datatype = 'normalized_degree_centrality'`）
- **有向グラフ**: 入次数と出次数を別々に保存する場合は、`datatype` を `in_degree_centrality` と `out_degree_centrality` のように分けてください。
- **更新**: 既存の計算結果を更新する場合は、`ON CONFLICT (graph_id, datatype) DO UPDATE` を使用してアトミックに上書きします。