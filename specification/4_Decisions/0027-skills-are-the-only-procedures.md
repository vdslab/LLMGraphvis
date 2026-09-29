# 0027. 手順は Skill だけに置き、すべてのツールを Skill から到達可能にする

- **状態**: 採用
- **日付**: 2026-09-29

## 背景

モデルに「どう進めるか」を渡す仕組みが二つあった。backend の Skill
（`skills/definitions/*.md`、`skill_load` で読み込み、`related_tools` を公開する）と、
networkx-api の MCP プロンプト（`app/mcp/prompts.py`、`list_prompts` / `get_prompt`
というクライアント側ツール経由で読める）である。

MCP プロンプトは Skill 導入後に更新されておらず、非推奨の
`analysis_detect_communities` を勧め、旧来の自動切替ツールの後に
`visualization_switch_network` を重ねて呼ぶよう指示していた。これは
`subgraph-workflow` Skill の「切り替えを重ねない」と矛盾する。

また、ツールは段階的公開（ADR 0010）で、初期公開は `skill_load` / `tool_search` /
`ask_user` のみである。監査の時点で、MCP ツール 81 個のうち 20 個はどの Skill の
`related_tools` にもなく、`tool_search` でしか見つからなかった（近接中心性・
固有ベクトル中心性・橋・切断点・有向グラフの連結成分など）。Skill 本文が呼べと
指示しながら公開していないツールもあり、`guard_tool_is_exposed` に拒否されて
1往復を失っていた。Skill が存在しない引数名（`gain_threshold`）を挙げている例もあった。

## 決定

1. MCP プロンプトを廃止する。`app/mcp/prompts.py` と、backend の `list_prompts` /
   `get_prompt` ツールを削除する。手順は Skill だけに書く。
2. networkx-api は全ツールの名前と引数名を `common/mcp_tools.json` に書き出す
   （`python -m app.mcp.manifest`）。両コンテナが `common/` をマウントしているので、
   backend のテストはこれを読んで Skill を検査できる。
3. backend の `tests/test_skill_tool_references.py` が次を強制する。
   - `related_tools` と本文に書かれたツール名が実在する。
   - 本文が呼べと言うツールは、その Skill か、本文が名前で指す Skill が公開している。
   - `tool(param=...)` と `tool.param` の引数名が実在する。
   - 非推奨でないツールはすべて、どれかの Skill から公開されるか、理由付きの
     `SEARCH_ONLY` に載っている。
4. 公開されていなかった指標ツール群のために `network-metrics` Skill を追加する。
5. `analysis_detect_communities` を `DEPRECATED_TOOL_NAMES` に加える。

## 根拠

- 二重管理は片方が必ず陳腐化する。Skill 側にはトリガー、段階的公開、
  テストがそろっており、MCP プロンプトには何もない。MCP プロンプトを Skill の
  生成元にする案は、Skill が backend 固有の概念（`ask_user`、チューニングパネル）
  に依存するため採らなかった。
- 名前の照合を MCP サーバーへの実接続で行う案は、テストがサービス起動に
  依存するので採らなかった。マニフェストはファイル一つで済み、陳腐化は
  networkx-api 側のテストが検出する。

## 帰結

- ツールを追加・改名したら `python -m app.mcp.manifest` を実行する。
  忘れると networkx-api の `test_tool_manifest.py` が落ちる。
- 新しいツールは Skill の `related_tools` に入れるか、`SEARCH_ONLY` に理由付きで
  載せない限り backend のテストが落ちる。
- 本文中の引数の検査は `tool(param=...)` と `tool.param` の形だけが対象である。
  散文中の引数名は検査されない。
