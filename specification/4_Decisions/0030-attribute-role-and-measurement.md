# 0030. 属性に役割と尺度を持たせ、エンコーディングをそこから選ぶ

- **状態**: 採用
- **日付**: 2026-10-10

## 背景

LLM は DB を直接読まない。エージェントが属性について知ることは、毎ターン
システムプロンプトに付く `[Current Network Context]`（`llm/context.py`）と、
MCP リソース・ツールの戻り値がすべてである。したがって「LLM が認識しやすい DB」
とは、テーブルの形ではなく、**DB が属性の意味を持っていて、それがこの経路で
届くこと**を指す。

属性定義が持っていた型は `data_type` だけで、これは値を格納するテーブル
（`float` か `string`）を表すにすぎない。インポート時、数値なら `float`、
それ以外は `string` に潰していた。整数のグループ番号と中心性はどちらも
`float`、人名とクラブ名はどちらも `string` に見える。エンコーディングの選択に
必要な「値どうしをどう比べられるか」が DB のどこにもなかった。

実データで確認すると、ほかにも次の問題があった。

- レイアウト座標 `{layout}_x` / `{layout}_y` が通常の属性として数えられ、
  15 件で打ち切る属性一覧から元データの属性を押し出していた。
  ネットワーク 1 では 3 件が `... and 3 more` に隠れていた。
- 来歴（`is_derived` / `derived_from`）を記録し始めた 2026-07 より前に計算された
  699 行には来歴がなく、計算したコミュニティが元データとして表示されていた。
- サブグラフへの複製では来歴が落ち、保持したレイアウト座標が元データ扱いになっていた。
- 派生属性の計算パラメータは保存されていたが、LLM には届いていなかった。

## 決定

`node_attributes` と `edge_attributes` に 2 列を加える。

- `role`（なぜその属性があるか）: `data` / `metric` / `community` / `coordinate`
- `measurement`（値をどう比べられるか）: `categorical` / `discrete` /
  `quantitative` / `identifier` / `text`

値の決め方は由来で分ける。

- **派生属性**は、書き込んだ計算が両方を決める。すべての派生属性は
  `update_attribute_cache_metadata` を通るので、`derived_from` の接頭辞
  （`centrality:` / `community:` / `layout:`）から 1 か所で決める。
- **元データの属性**は、インポート時に値から `measurement` を推定して保存する。
  推定の前からある行は、最初に一覧されたときに推定して保存する。

LLM への見せ方を変える。

- 属性は `name (storage type, measurement)` と表示し、派生属性にはパラメータを添える。
- 座標は属性一覧から外し、`Computed layouts: forceatlas2, spring` の 1 行にする。

尺度に合わないエンコーディングは**拒否せず、警告する**。色・サイズ・太さの
ツールは、描いた尺度が属性の `measurement` と合わないとき、戻り値に
`encoding_note` を含める。`visual-encoding` スキルは、尺度からチャネルを選ぶ表を持つ。

マイグレーションは、来歴のない古い行を、計算が付ける名前
（`{layout}_x`、`{algorithm}_community`）から判別して来歴も補う。複製時は
役割・尺度・来歴を引き継ぎ、キャッシュの刻印（グラフのハッシュ）は引き継がない。

## 根拠

**尺度の語彙.** 可視化の文献にある名義・順序・量の 3 分類をそのまま使わず、
値から推定できるものに限った。

- `ordinal`（順序）を置かない。1〜5 の評定と 1〜5 のグループ番号は値だけでは
  区別できず、推定できない値を列に書けば、正しいふりをした誤りになる。
- 代わりに `discrete` を置く。「少数の整数で、番号かもしれないし個数かもしれない」
  という曖昧さをそのまま名前にし、判断を名前と説明文を読める LLM に委ねる。
- `identifier` と `text` を分ける。どちらもエンコードには使わないが、前者は
  ラベルに、後者は読んで引用するのに使う。

**却下案 A: EAV をやめて JSONB などに作り替える.** LLM は DB の形を見ないので、
エージェントの理解は変わらない。性能と保守性の問題であり、今回の目的とは別である。

**却下案 B: 一覧のたびに値から推定し、DB には持たない.** 毎回すべての値を
読むことになる。さらに、DB を読む者（ツール、将来の修正手段、人）によって
答えが変わりうる。推定は一度だけ行い、結果を事実として保存する。

**却下案 C: 合わないエンコーディングをフックで拒否する.** 利用者が意図して
珍しい対応付けを求めることがある（ユーザー主権）。また `discrete` は判定できない。
拒否は回復のための往復を生むが、警告なら同じ応答の中で直せる。

**却下案 D: アップロード時に LLM に属性を分類させる.** アップロードのたびに費用と
待ち時間がかかり、結果が揺れる。決定的な推定で足り、誤りは LLM が名前と説明文で
補正できる。修正手段（尺度を上書きするツール）は、運用で必要になってから加える。

## 帰結

- 派生属性を書く新しい経路も、必ず `update_attribute_cache_metadata` を通す。
  新しい `derived_from` 接頭辞は `attribute_semantics._ROLE_BY_SOURCE` に加える。
  加えなければ `metric` として扱われる。
- 推定のしきい値は `networkx-api/app/logic/attribute_semantics.py` にだけ置く。
- 語彙は `attribute_semantics.py`（正）、列の `comment`、マイグレーションの
  補完表に現れる。マイグレーションのものはその時点の写しであり、追従させない。
- `context.py` は `role` で座標を判別し、`role` を持たない旧サーバーの一覧に
  限って名前の規則にフォールバックする。
- 実装: `common/models.py`、`backend/alembic/versions/c1d2e3f4a5b6_attribute_semantics.py`、
  `networkx-api/app/logic/{attribute_semantics,attributes,importer}.py`、
  `utils/attribute_copier.py`、`mcp/tools/visualization/style.py`、
  `backend/app/services/llm/context.py`、スキル `visual-encoding` / `analysis-planning`。
