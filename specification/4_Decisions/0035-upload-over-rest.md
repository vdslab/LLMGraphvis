# 0035. アップロードは REST、会話は MCP

- **状態**: 採用
- **日付**: 2026-10-23

## 背景

アップロード後の初期化（import、初期レイアウト、初回描画）を、backend は MCP ツール
（`network_import_graphml`、`layout_forceatlas2`、`visualization_generate`）として
呼んでいた。

MCP の SSE トランスポート（`mcp` 1.30）は、4 MiB を超える POST を `413` で拒否する。
4.6MB の GraphML をアップロードすると、ツール呼び出しが networkx-api に届かずに拒否された。
MCP クライアントは 413 を例外として返さないので、backend は来ない応答を待ち続け、
画面は「Importing GraphML data」のまま止まった。一方、アップロードの受付と networkx-api の
REST 経路は、上限を 50MB としている。経路によって上限が違っていた。

## 決定

- **ユーザーの操作は REST で行う。** アップロード時の初期化は、backend から networkx-api の
  REST を順に呼ぶ（`network_service`）。
  - `POST /api/v1/networks/{id}/import`：GraphML を JSON に包まず、XML の本文のまま送る。
    上限は 50MB。
  - `POST /api/v1/networks/{id}/layout`：既存のルート。
  - `GET /api/v1/networks/{id}/visualization`：`visualization_generate` と同じ組み立てを返す。
- **エージェントの判断は MCP で行う。** 会話の中の解析・レイアウト・描画は、これまでどおり
  MCP ツールと skill で進める。
- REST と MCP は、同じロジック関数（`importer.parse_and_save_graphml`、
  `layout.calculate_layout`、`visualization_builder.build_visualization`）を呼ぶ。
  入口が違っても結果は変わらない。
- アップロード後の概要表示は、MCP リソースの読み取りのまま残す。小さな読み取りなので上限に
  当たらず、毎ターンの文脈要約と同じ読み方を共有している。

## 根拠

- 分ける基準は「誰が決めた操作か」である。ファイルを選んだのはユーザーで、そこにモデルの
  判断はない。GraphML の export も同じ理由で REST にしている（`network_service.export_graphml`）。
- MCP はモデルとツールの対話のための経路である。数 MB の文書を運ぶ経路にすると、
  プロトコル側の上限やエラーの扱いに縛られる。
- 却下した代替案：
  - **MCP の本文上限を 50MB に引き上げる**：1 行で直るが、モデルが使わない数 MB の文書を
    MCP で運び続けることになる。今後上限が変わっても、また同じ所で止まる。
  - **既存の `POST /initialize` を使う**：import とレイアウトをまとめて行うので、段階ごとの
    進捗表示ができない。レイアウトも固定になる。

## 帰結

- アップロードの上限は、受付と networkx-api の 50MB に統一される。
- MCP ツールの `network_import_graphml` は会話用に残す。その経路では 4 MiB の上限が残る。
- 実装：`networkx-api/app/api/v1/endpoints/networks.py`、`visualization.py`、
  `backend/app/services/network_service.py`、`chat_service.handle_upload_background`。
