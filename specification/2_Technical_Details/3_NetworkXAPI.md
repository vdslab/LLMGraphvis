# 3. ネットワーク計算サービス仕様 (NetworkXAPI)

**前提知識レベル:**
- マイクロサービスの概念
- NetworkXライブラリに関する知識
- FastAPIに関する開発経験

NetworkXAPIは、ネットワークに関する計算処理と、その結果の永続化に特化した**MCP (Model Context Protocol) サーバー**です。FastAPI上で動作し、SSE (Server-Sent Events) を通じてツールを公開します。

## 3.1. 役割

- **MCP Server**: GenAIのための標準化されたインターフェース（MCP）を提供し、Tools (Act), Resources (Read), Prompts (Template) を通じて機能を提供する。
- **ステートレス計算**: 内部状態を持たず、計算結果は全てデータベースに永続化する。
- **SSEエンドポイント**: `/mcp/sse` エンドポイントを通じてMCPプロトコルによる通信を行う。

## 3.2. ツール定義 (MCP Tools)

本サーバーが提供するMCPツール、およびクライアント側（Backend）で提供されるユーティリティツールの定義です。

### 3.2.0. Client-Side Utility Tools (Backend提供)

これらはNetworkXAPIサーバー自体には実装されていませんが、MCPクライアント(Backend)がアダプターとして提供し、LLMが利用可能なツールです。

#### `read_resource(uri: str)`
- **説明**: MCPサーバー上のリソース（データ）を直接読み込みます。LLMは計算や可視化を行う前に、このツールを使ってデータの存在や内容（例：属性リスト）を確認することが義務付けられています。
- **引数**:
  - `uri`: リソースURI (例: `network://1/attributes/nodes`)

### 3.2.1. Server-Side MCP Tools (NetworkXAPI提供)

ツールは `networkx-api/app/mcp/tools/{domain}/` 配下の `@mcp.tool()` 付き関数から
**自動的に検出**される。別途スキーマを登録する箇所は存在しない。命名規則は
`domain_verb`。

| Prefix | 数 | 責務 |
|:---|:--:|:---|
| `network_*` | 7 | ネットワーク単位のインポート・メタデータ・属性一覧 |
| `node_*` | 6 | 単一ノードの検索・詳細・近傍・フィルタ・改名 |
| `subgraph_*` | 8 | 部分グラフの作成（フィルタ / 明示リスト / エゴ / k-core / コミュニティ / 最大連結成分 / 高次数） |
| `analysis_*` | 8 | 属性として保存される計算指標（中心性各種・コミュニティ検出・クラスタ係数・最短経路） |
| `layout_*` | 13 | ノード座標の計算（力学系・幾何・構造ベース） |
| `visualization_*` | 10 | スタイル設定・レンダリング・状態取得・スタイルリセット・表示ネットワーク切替 |

**合計 52 ツール。** 各ツールの引数・既定値・戻り値は実装の docstring と
`Field(description=...)` を**唯一の情報源**とする。本仕様書がそれを複製すると
必ず乖離するため、ここでは列挙しない（実際、本節は刷新前のツール名のまま長期間
放置されていた）。現在のツール一覧は次で取得できる。

```bash
cd networkx-api && python -c "
import app.mcp_server, asyncio
from app.core.mcp import mcp
print(sorted(t.name for t in asyncio.run(mcp.list_tools())))"
```

#### レイアウトツール (13)

| ツール | 種別 | 備考 |
|:---|:---|:---|
| `layout_forceatlas2` | 力学系 | **既定**。反復ごとに密な斥力計算（O(N^2)、Barnes-Hut 近似なし）のため `max_iter` が実行時間を支配する |
| `layout_spring` | 力学系 | Fruchterman-Reingold。ノード間隔がより均等 |
| `layout_arf` | 力学系 | 引力・斥力を個別制御。ForceAtlas2 で重なりが残る場合の第二候補 |
| `layout_kamada_kawai` | 数理 | 大域構造に優れるが密な N×N 距離行列を構築するため時間・メモリともに O(N^2)。閾値超はフックが拒否する |
| `layout_spectral` | 数理 | ラプラシアンの固有ベクトル。高速・決定的だが密なグラフでは退化しやすい |
| `layout_circular` / `layout_shell` / `layout_spiral` / `layout_random` | 幾何 | 位相構造を反映しない。`layout_shell` は `nlist` を与えて初めて意味を持つ |
| `layout_bipartite` / `layout_multipartite` | 構造 | 属性による分割を軸に配置。属性値は DB から読み出してグラフに付与される |
| `layout_planar` | 構造 | 平面グラフ限定。非平面入力では代替を案内するエラーになる |
| `layout_bfs` | 構造 | 根からの BFS 距離で階層化 |

**パラメータの許可リスト**: `app/logic/layout.py` の `LAYOUT_PARAM_KEYS` が、各
networkx 関数に渡してよい引数名を定義する。ここに無い引数は nx に到達せず、
逆にここにある引数は握り潰されない。パラメータを新たに公開する際は、この辞書と
ツール署名の両方を更新すること（`tests/test_layout_parameters.py` が許可リストを
インストール済み networkx のシグネチャと突き合わせる）。

**独自パラメータ**: `init_from_layout`（既存レイアウト名を指定してウォーム
スタート。座標 dict を LLM に書かせるのは非現実的なため名前で指定する）、
`partition_attribute` / `partition_value` / `subset_attribute`（分割属性を
nx の `nodes` / `subset_key` に解決する）。

**注意すべき仕様**:
- レイアウトは座標を保存するだけで描画しない。`visualization_generate` を続けて呼ぶ。
- `scale` / `center` は**視覚的に無効**。描画前に座標が [-1000, 1000] に再正規化されるため。
- `weight` を明示的に渡さない限り**エッジ重みは無視される**。`build_graph_from_db` が
  既定では weight 属性を載せないため、nx 側の既定値 `weight="weight"` が空振りする。
- 結果は「グラフ構造ハッシュ + 実効パラメータ」でキャッシュされる。パラメータを
  変えれば自動的にキャッシュミスとなるため、`force_recompute` は利用者が明示的に
  再計算を求めた場合のみ使う。ノード数に比例する巨大なパラメータ（`pos`, `nodes`,
  `node_size` など）はダイジェスト化して保存する。

#### 非推奨ツール

後方互換のため残しているが新規利用は避けること。

| ツール | 理由 | 代替 |
|:---|:---|:---|
| `network_initialize` | パース・レイアウト・描画の3責務が結合し、レイアウトが ForceAtlas2 固定 | `network_import_graphml` → 任意の `layout_*` → `visualization_generate` |
| `visualization_apply_layout` | `visualization_generate` と実装が完全に同一 | `visualization_generate` |

## 3.3. MCPリソース一覧 (Resources)

モデルが**参照**する読み取り専用データです。クライアント（LLM Service）は `read_resource(uri)` ツールを通じてこれらにアクセスします。
 
| Resource URI | 説明 |
|:---|:---|
| `network://{id}/metadata` | ネットワークのメタデータ（ID, 名前, 説明, 作成日時）をJSON形式で取得する。 |
| `network://{id}/graphml` | ネットワークの完全なGraphMLデータを取得する。 |
| `network://{id}/attributes/nodes` | 利用可能なノード属性（名前, 型, 統計情報）の一覧を取得する。 |
| `network://{id}/attributes/edges` | 利用可能なエッジ属性（名前, 型, 統計情報）の一覧を取得する。 |
| `network://{id}/subgraphs` | 親ネットワークから作成されたサブグラフの一覧を取得する。 |
| `network://{id}/centrality/{metric}/top` | 指定された中心性指標（metric）の上位ノードを取得する。オプションパラメータには対応しないため、デフォルト設定（TOP 10）等を返す。 |
| `network://{id}/structure` | ネットワークの基本構造情報（ノード数、エッジ数、密度、連結成分数など）を取得する。 |

## 3.4. MCPプロンプト一覧 (Prompts)

モデルに対する**定型的な指示セット**です。分析の開始点や、特定のタスク（可視化提案など）を行う際に使用されます。

| Prompt Name | Arguments | 説明 |
|:---|:---|:---|
| `analyze-structure` | `network_id` | ネットワークの構造的特徴（密度、連結性など）を分析し、全体像を把握するよう指示するメッセージセットを返す。 |
| `recommend-visualization` | `network_id` | 利用可能な属性と構造に基づいて、最適な可視化（レイアウト、色、サイズ）を提案するよう指示するメッセージセットを返す。 |
| `investigate-attributes` | `network_id` | 特定のノードやエッジの属性に注目し、異常値や特徴的なパターンを探すよう指示するメッセージセットを返す。 |
| `find-important-nodes` | `network_id` | 複数の中心性指標や属性を組み合わせて、ネットワーク内の重要ノード（インフルエンサー、ハブなど）を特定し、その理由を説明するよう指示するメッセージセットを返す。 |
| `search_nodes` | `network_id`, `query`, `attribute` | ノード名（ID、ラベル）または特定の属性値でノードを検索する。検索結果には、マッチした値も含まれる。 |

## 3.5. ツール定義詳細

各ツールの引数・既定値・戻り値は、実装側の docstring と
`Field(description=...)` を唯一の情報源とする。これらは MCP のスキーマとして
LLM にそのまま送られる「プロンプト表面」であり、本仕様書に転記した写しは
必ず陳腐化する（本節は以前まさにそうなっていた）。3.2.1 のコマンドで
現在の定義を取得すること。

以下は、署名からは読み取れない**横断的な規約**のみを記す。

- **`size` は半径ではなく面積**。フロントエンドは `r = sqrt(size * 10 / π)` で
  描画する（`NetworkGraph.jsx`）。この換算はツール記述・`visualization_builder`・
  フロントエンドの3箇所に現れるので、変更時は同時に更新する。
- **スタイルは維持される**。`visualization_set_*` は渡されなかったチャネルを
  DB から復元する。`_save_state` は非 None のみ書き込むため、**設定ツールでは
  スタイルを解除できない**。`visualization_reset_style` が唯一の解除手段。
- **派生属性名**。`analysis_detect_communities` は `{algorithm}_community`、
  レイアウトは `{layout}_x` / `{layout}_y` に保存する。固定名を仮定せず、
  ツールの戻り値メッセージから正確な名前を読む。
- **部分グラフ作成ツールは `new_network_id` を返す**。Backend の POST_TOOL フック
  がこれを検出して自動的に描画と表示切替を行うため、ツール自身は描画しない。

## 3.6. REST API エンドポイント (MCP Feature Parity)

MCPツールと同等の機能をREST API経由でも利用可能にするため、以下のエンドポイントを提供します。これらは `endpoints/networks.py`, `endpoints/subgraphs.py` 等で定義されています。

### ネットワーク管理 (`/api/v1/networks`)

| Method | Path | 説明 |
| :----- | :--- | :--- |
| `POST` | `/initialize` | GraphMLデータを受け取り、ネットワークを初期化（パース、保存、初期レイアウト計算）する。 |
| `GET` | `/{network_id}/metadata` | ネットワークのメタデータ（名前、説明、視覚状態）を取得する。 |
| `PUT` | `/{network_id}/metadata` | ネットワークのメタデータを更新する。 |
| `GET` | `/{network_id}/export` | ネットワークをGraphML形式でエクスポートする。 |

### ネットワーク分析・検索 (`/api/v1/networks`)

| Method | Path | 説明 |
| :----- | :--- | :--- |
| `GET` | `/{network_id}/attributes/nodes` | 利用可能なノード属性（統計情報含む）の一覧を取得する。 |
| `GET` | `/{network_id}/attributes/edges` | 利用可能なエッジ属性（統計情報含む）の一覧を取得する。 |
| `GET` | `/{network_id}/nodes/search` | クエリ文字列または属性値でノードを検索する。 |
| `GET` | `/{network_id}/subgraphs` | ネットワークから派生したサブグラフの一覧を取得する。 |

### サブグラフ作成 (`/api/v1/networks/{network_id}/subgraphs`)

| Method | Path | 説明 |
| :----- | :--- | :--- |
| `POST` | `/ego` | Ego Networkを作成する。 |
| `POST` | `/from-nodes` | 指定ノード群からサブグラフを作成する。 |
| `POST` | `/path` | 最短経路サブグラフを作成する。 |
| `POST` | `/k-core` | K-Coreサブグラフを作成する。 |
| `POST` | `/largest-component` | 最大連結成分サブグラフを作成する。 |
| `POST` | `/component-containing-node` | 指定ノードを含む連結成分サブグラフを作成する。 |
| `POST` | `/filter` | 属性条件に基づいてノードをフィルタリングし、サブグラフを作成する。 |


## 3.7. 内部実装構造 (Refactoring Notes)

コードの保守性と可読性を向上させるため、以下のリファクタリングを実施しました。

### 3.7.1. VisualizationBuilder (`app.logic.visualization_builder`)
- **目的**: 以前は `visualizer.py` に存在した400行を超える巨大な可視化生成ロジックをクラス化し、責務を分離しました。
- **機能**:
  - `validate_and_prepare`: 設定の検証と初期化
  - `fetch_data`: 必要なノード・エッジデータの取得
  - `calculate_statistics`: 統計情報の計算とカラーマップの生成
  - `build`: 最終的なJSON構造の構築

### 3.7.2. StyleService (`app.logic.style_service`)
- **目的**: 色やサイズの計算ロジックを集約しました。
- **改善点**:
  - `prepare_categorical_map`: カテゴリカルカラーの自動割り当てロジックを改善。`default_color` が指定された場合でも自動割り当て（Autofill）を行い、上位の頻出値にはパレット色を、それ以外にはデフォルト色を適用する「Hybrid Mode」として動作するように変更しました。これにより、明示的なマッピングがない頻出カテゴリも区別可能になります。

### 3.7.3. NetworkService (`app.logic.network_service`)
- **目的**: `mcp_server.py` に記述されていたビジネスロジック（メタデータ更新、構造取得、サブグラフ一覧取得など）を専用のサービス層に移動しました。これにより、MCPサーバーコードはルーティングとツール定義に集中できるようになりました。

### 3.7.4. MCP Tools Package (`app.mcp.tools`)
- **目的**: 巨大化した `tools.py` を機能ごとに分割し、パッケージ化しました。
- **構造**:
  - `initialization.py`: ネットワーク初期化・インポート関連 (`initialize_network`, `import_graphml`)
  - `computation.py`: 計算処理 (`calculate_centrality`, `calculate_layout`, `calculate_community`)
  - `subgraph.py`: サブグラフ作成・フィルタリング (`create_X_subgraph`, `filter_nodes`)
  - `visualization.py`: 可視化生成・更新 (`generate_visualization`, `update_node_color`, etc.)
  - `retrieval.py`: 情報検索・参照 (`search_nodes`, `get_top_nodes`, `list_attributes`)
- **特徴**: `Annotated` と Pydantic (`Field`) を使用し、LLM向けの正確な JSON Schema を生成可能な定義スタイルに統一しました。
