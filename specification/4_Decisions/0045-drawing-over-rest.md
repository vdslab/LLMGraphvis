# 0045. 描画データは REST で運び、MCP の結果は受領結果だけにする

- **状態**: 採用
- **日付**: 2026-11-10

## 背景

描画系の MCP ツール（`visualization_generate`、`visualization_set_*`、
`visualization_highlight`、`visualization_set_viewport`、`visualization_reset_style`、
`visualization_switch_network`）は、描画データの全体（全ノードと全エッジ）を結果として
返していた。backend はその結果をそのままブラウザへ流していた。

MCP の Streamable HTTP クライアント（`mcp` 2 系）は、1 イベントが 1 MiB を超えると
ストリームを打ち切る。3,393 ノード・5,119 エッジのネットワークで
`visualization_set_node_color` を呼ぶと、結果がこの上限を超えた。backend はこれを
接続断として扱い、モデルに「再実行して安全」と伝えたので、同じ失敗が繰り返された。

ADR 0035 はアップロード（backend → networkx-api の入力）を REST に移した。
今回は逆方向で、ツールの結果が同じ種類の上限に当たった。モデルはノードとエッジの行を
読まない。`observations.py` が件数に置き換えてから渡していた。

## 決定

経路ごとに、運ぶものを次のように決める。

| 経路 | 方式 | 運ぶもの |
|---|---|---|
| ブラウザ → backend | REST | アップロード、チャット操作、DB への追加 |
| backend → ブラウザ | SSE | チャットの進行と描画データ |
| backend ↔ networkx-api | MCP | モデルが決めた操作と、モデルが読む結果 |
| backend → networkx-api | REST | 描画データの全体、GraphML の import と export |
| ブラウザ → networkx-api | なし | 接続しない |

- **描画系ツールは受領結果を返す。** 受領結果は `rendered: true`、`network_id`、
  `node_count`、`link_count` と、描画データのうちノードとエッジの行以外のすべて
  （`legend`、`layout_quality`、`viewport`、`encoding_note` など）からなる
  （`visualization_builder.drawing_receipt`）。
- **描画データの全体は REST で取る。** backend は受領結果を見て
  `GET /api/v1/networks/{id}/visualization` を呼び、受領結果の項目を重ねてから
  ブラウザへ送る（`llm/drawing.py`）。品質指標は受領結果にあるので、この取得では
  計算を省く（`quality=false`）。
- **backend が自分で描き直す場合も REST を使う。** サブグラフへの切り替えやラベル変更の
  後の再描画は、`visualization_generate` を MCP で呼ばず、同じ REST を呼ぶ。
- **結果が上限を超えたら、接続断とは別のエラーにする。** `ToolResultTooLarge` は
  再実行を勧めず、`limit` などで結果を絞るように伝える。
- 開発用の `/nx-api` プロキシは削除する。ブラウザから networkx-api へ直接つながる
  経路をなくす。

## 根拠

- 分ける基準は ADR 0035 と同じで、「モデルが読むかどうか」である。モデルが読むのは
  件数、凡例、品質指標で、ノードとエッジの行はブラウザだけが使う。
- スタイルは保存される（`_save_state`）ので、REST で組み立て直しても同じ絵になる。
  保存されない項目（一回限りの `viewport` など）は受領結果に残るので、失われない。
- モデルが見る結果は変わらない。受領結果は、`observations.py` がこれまで描画データから
  作っていた形と同じである。
- 却下した代替案：
  - **MCP クライアントの上限を引き上げる**：ネットワークが大きくなれば、また同じ所で
    止まる。モデルが読まないデータを MCP で運び続けることにもなる。
  - **ブラウザが描画データを直接取りに行く**：SSE では小さな通知だけを送り、ブラウザが
    REST で取得する形。SSE にはブラウザ側の上限がなく、今は困っていない。返答との
    順序を保つ仕組みが別に必要になるので、見送った。
  - **backend が DB から描画データを組み立てる**：組み立てのロジックが二つの
    サービスに分かれる。

## 帰結

- 描画系ツールの結果は、ノード数とエッジ数に比例して大きくならない（ADR 0024 と同じ
  方針）。凡例のカテゴリ数には比例する。
- 描画系ツールは、スタイルを保存してから受領結果を返す。保存されない項目を描画データに
  足すときは、受領結果に入れる。入れなければブラウザに届かない。
- 描画のたびに組み立てが 2 回走る（ツールの中と REST）。品質指標の計算は 1 回である。
- 非推奨の `network_initialize` は描画データをそのまま返す。古い会話のために残して
  あるだけなので、変更しない。
- 会話中の `network_import_graphml` には、MCP の入力側の上限が残る（ADR 0035）。
- 実装：`networkx-api/app/logic/visualization_builder.py`、
  `networkx-api/app/mcp/tools/visualization/`、
  `networkx-api/app/api/v1/endpoints/visualization.py`、
  `backend/app/services/llm/drawing.py`、`hooks/builtin/side_effects.py`、
  `llm/tuning.py`、`llm/mcp_client.py`、`backend/app/services/network_service.py`。
