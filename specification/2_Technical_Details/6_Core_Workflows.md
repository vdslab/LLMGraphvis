# 6. 主要な処理フローとデータ生成

**前提知識レベル:**
- シーケンス図の読解能力
- REST APIおよびSSEに関する知識
- LLMのFunction Calling（ツール呼び出し）に関する基本的な理解

## 6.1. 概要

このドキュメントでは、主要なユースケースにおけるコンポーネント間の動的なやり取りと、その過程で実行されるデータ生成のフローを定義します。

本システムのコア機能は、ユーザーの自然言語指示をLLMが解釈し、複数のツールを段階的に呼び出すことで、最終的なネットワークの可視化を実現する点にあります。

---

## 6.2. 新規チャット作成とネットワークの初期化フロー

**目的:** ユーザーが新しい分析サイクルを開始するフローを、**チャット作成**と**ネットワークデータ初期化**の2段階に分離して定義します。これにより、責務が明確になり、よりRESTfulな設計を実現します。

**方針:** ネットワークデータの処理は時間がかかる可能性があるため、**非同期処理**を維持します。入力はユーザーのGraphMLファイルと同梱サンプルの二つを認めますが、どちらもBackendでGraphML文字列へ解決した後は同じ処理へ合流させます。これにより、入力方法によって属性型推論、初期レイアウト、概要表示が変わることを防ぎます。Backendはリクエストを即座に受け付け、バックグラウンドでNetworkXAPIを呼び出します。完了後はSSEを通じてクライアントに通知します。

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service (Backend)
    participant N as NetworkXAPI (MCP Server)
    participant DB as Database

    %% Step 1: User creates a new chat
    U->>F: 「新規チャット」ボタンをクリック
    F->>B: POST /chat (body: { "name": "新しいチャット" })
    B->>DB: 1. 新しい`chats`レコードを作成
    DB-->>B: chat_id
    B->>DB: 2. `chats`に紐づく空の`networks`レコードを作成
    DB-->>B: network_id
    B-->>F: 作成応答 (chat_id, network_id)

    %% Step 2: Frontend navigates and user chooses an input
    F->>F: チャットページ(`/chat/{chat_id}`)へ遷移
    note right of F: アップロードとサンプル選択を表示
    U->>F: GraphMLファイルまたは同梱サンプルを選択
    alt GraphMLファイル
        F->>B: GraphMLデータを送信
    else 同梱サンプル
        F->>B: サンプルIDを送信
        B->>B: 許可リストから同梱GraphMLを解決
    end

    %% Step 3: Backend accepts the request and starts background task
    B-->>F: 202 Accepted
    note right of B: FastAPIのBackgroundTasksを使い、<br/>後続の重い処理をバックグラウンドで実行
    B->>N: GraphMLのインポート、レイアウト、描画を順次要求
    note right of B: 両入力で同じ初期化処理を使用

    %% Step 4: Frontend waits for SSE event
    F->>B: GET /chat/{chat_id}/stream
    note right of F: SSE接続を確立し、<br/>ネットワークの初期化完了を待つ。<br/>この間、ローディング画面などを表示。

    %% Step 5: Background processing in NetworkXAPI
    N->>N: 1. GraphMLを正規化<br/>(属性型の推論とdata_typeの決定)
    N->>DB: 2. ノードとエッジをDBに保存<br/>(値は型別のテーブルへ)
    DB-->>N: 保存成功
    N->>N: 3. 初期レイアウト(ForceAtlas2)を計算
    N->>DB: 4. 計算したx, y座標を属性として保存
    DB-->>N: 保存成功
    N->>N: 5. デフォルトスタイルを適用した<br/>初期レンダリングデータを生成
    N-->>B: 実行成功応答 (initial_render_data)

    %% Step 6: Backend forwards the initial data via SSE
    B-->>F: SSEイベント (event: render_update, data: initial_render_data)
    note right of F: SSEイベントを受け取り、<br/>ペイロード内のデータでネットワークを描画する。
```

---

## 6.3. チャットによるネットワーク操作（統一非同期フロー）

**目的:** ユーザーの自然言語指示に対し、Backendがリクエストを即座に受け付け、その後の全ての処理（LLMの思考、ツールの実行、最終的な応答）をSSEを通じてリアルタイムにクライアントへ通知する、統一された非同期フローを定義します。これが、本システムにおける唯一の信頼できるチャット操作フローです。

### 6.3.1. シーケンス図（統一非同期アーキテクチャ）

このフローでは、ブロッキングなHTTP応答は存在せず、全ての情報がSSEストリームを通じて伝達されるため、高い応答性とリアルタイム性を実現します。

```mermaid
sequenceDiagram
    autonumber
    %% Participants
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service (Backend)
    participant LLM as LLM Service
    participant N as NetworkXAPI (MCP Server)
    participant DB as Database

    note over F, B: このフローが開始される時点で、クライアントは<br/>既にSSE接続を確立済みであるとする。

    U->>F: 「友達が多い人を大きく表示して」
    F->>B: POST /chat/{id}/process (message)
    B->>DB: ユーザーメッセージを保存
    B-->>F: 202 Accepted
    note right of B: リクエストを即座に受け付け、<br/>以降の処理はバックグラウンドで実行。

    %% Step 1: Backend starts the process and streams thinking
    B->>LLM: ユーザー指示、チャット履歴、ツールリストを送信
    B-->>F: SSEイベント (event: thinking_stream, data: "ユーザーの意図を解釈中...")
    note right of LLM: ユーザー指示を解釈し、<br/>可視化の全体計画を立てる。
    LLM-->>B: ツール呼び出し要求 (1. read_resource)

    %% Step 2: Backend executes tools and streams status
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "read_resource", status: "started" })
    B->>N: Call MCP Tool: read_resource (uri: "network://.../attributes/nodes")
    N->>DB: 属性テーブル群から属性名一覧をクエリ
    DB-->>N: 属性リスト
    N-->>B: 属性リスト（例: [{name: 'weight'}, {name: 'community_id'}]）
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "read_resource", status: "completed" })

    %% Step 3: Backend continues planning with LLM
    B->>LLM: 属性リストをツール実行結果として送信
    LLM-->>B: ツール呼び出し要求 (2. analysis_degree_centrality)

    %% Step 4: Backend executes analysis_degree_centrality
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "analysis_degree_centrality", status: "started" })
    B->>N: Call MCP Tool: analysis_degree_centrality
    N-->>B: 計算完了
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "analysis_degree_centrality", status: "completed" })
    
    B->>LLM: ツール実行結果（成功）を送信
    LLM-->>B: ツール呼び出し要求 (3. read_resource)

    %% Step 5: Backend executes read_resource (Verification)
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "read_resource", status: "started" })
    B->>N: Call MCP Tool: read_resource
    N-->>B: 更新された属性リスト
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "read_resource", status: "completed" })

    B->>LLM: ツール実行結果（成功）を送信
    LLM-->>B: ツール呼び出し要求 (4. layout_forceatlas2)

    %% Step 6: Backend executes layout_forceatlas2 (Strict Requirement)
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "layout_forceatlas2", status: "started" })
    B->>N: Call MCP Tool: layout_forceatlas2
    N-->>B: 計算完了
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "layout_forceatlas2", status: "completed" })

    B->>LLM: ツール実行結果（成功）を送信
    LLM-->>B: ツール呼び出し要求 (5. visualization_generate)

    %% Step 7: Backend executes visualization_generate
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "visualization_generate", status: "started" })
    B->>N: Call MCP Tool: visualization_generate
    N-->>B: 最終レンダリングデータ { nodes: [...], links: [...] }
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "visualization_generate", status: "completed" })

    %% Step 7: Backend sends final data and text response via SSE
    B-->>F: SSEイベント (event: render_update, data: { nodes, links })
    note right of F: グラフの更新データを受け取り、<br/>即座に画面を再描画する。

    B->>LLM: ツール実行完了を報告
    LLM-->>B: 最終応答メッセージ（「次数中心性を計算し...なぜなら...」）
    B->>DB: LLMの応答を保存
    B-->>F: SSEイベント (event: message, data: { role: "assistant", content: "次数中心性を計算し...なぜなら..." })
    note right of F: テキスト応答を受け取り、<br/>チャット履歴に追加する。

    %% Step 8: Frontend renders the updated network
    F->>F: render(event.data.nodes, event.data.links)
```

### 6.3.2. データフローと責務詳細

この統一フローにおいて、フロントエンドは`POST /chat/{id}/process`を呼び出した後、HTTPレスポンスを待つことなく、即座に操作可能な状態を維持します。ローディング状態の管理は、SSEから送られてくる`tool_execution`イベントの`status`（`started`/`completed`）に基づいて行います。

1.  **リクエストの即時受付**:
    - Backendは`POST /chat/{id}/process`のリクエストを受け取ると、メッセージをDBに保存し、即座に`202 Accepted`を返す。これにより、フロントエンドはブロックされない。

2.  **LLMによるプランニングとツールの実行**:
    - LLMの思考プロセスや、`read_resource`、`analysis_degree_centrality`、`layout_forceatlas2`、`visualization_generate`といったツールの実行状況は、`thinking_stream`や`tool_execution`といった専用のSSEイベントを通じて逐一フロントエンドに通知される。
    - **重要**: LLMは計算を実行した後、必ず再度`read_resource`を呼び出して、新しい属性が利用可能になったことを確認してから`visualization_generate`を呼び出す。また、**「name」や「label」などの属性が存在する場合、それを識別可能なラベルとして自動的に選択する。**

3.  **最終的な結果の通知**:
    - `visualization_generate`が完了すると、Backendは2つの重要な情報をSSEで送信する。
        1.  `render_update`イベント: NetworkXAPIが生成した最終的なレンダリングデータ（`{nodes, links}`）を送信する。フロントエンドはこれを受けてグラフを再描画する。
        2.  `message`イベント: LLMが生成した最終的なテキスト応答（例：「次数中心性を計算し、ノードのサイズに反映しました。これにより、ネットワーク内で最も影響力のあるノードが視覚的に強調されます。」）を送信する。ここには、**なぜその計算を行ったのか、なぜその可視化設定を選んだのかという理由**が含まれるべきである。また、**ユーザーが入力した言語と同じ言語で応答する**ことが必須である。フロントエンドはこれを受けてチャット履歴を更新する。

この設計により、フロントエンドとバックエンドは完全に疎結合となり、ユーザーは処理の途中経過をリアルタイムに把握しながら、待たされることなくアプリケーションの操作を続けることができます。

---

## 6.4. ツール呼び出し失敗時のエラーハンドリングフロー

**目的:** システムが予期せぬ状況（例: 未実装の計算）に陥った場合でも、LLMが状況を理解し、ユーザーに代替案を提示することで、チャットを継続できるようにします。このフローも同様に非同期で実行されます。

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXAPI

    U->>F: 「Betweenness Centralityを計算して」
    F->>B: POST /chat/{id}/process (message)
    B-->>F: 202 Accepted

    B->>LLM: ユーザーの指示を送信
    LLM-->>B: ツール呼び出しを要求 (analysis_betweenness_centrality)

    B-->>F: SSEイベント (event: tool_execution, data: { tool: "analysis_betweenness_centrality", status: "started" })
    B->>N: Call MCP Tool: analysis_betweenness_centrality (network_id)
    note over N: 計算エラー発生（例：メモリ不足）
    N-->>B: 実行失敗の応答 (エラーメッセージ)
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "analysis_betweenness_centrality", status: "failed", error: "..." })

    B->>LLM: ツールの実行結果（失敗）を送信
    note right of LLM: LLMは失敗を認識し、<br/>ユーザーへの説明と代替案を生成する。
    LLM-->>B: 最終的な応答メッセージを生成 (例: 「申し訳ありません、Betweennessの計算に失敗しました。次数中心性など、他の指標ではいかがでしょうか？」)

    B-->>F: SSEイベント (event: message, data: { role: "assistant", content: "申し訳ありません..." })
    note right of F: グラフは変更せず、LLMからのエラーメッセージをチャット履歴に表示する。
```

---

## 6.5. ノード認識に基づくサブグラフ作成フロー

**目的:** ユーザーの「最も重要なノードのEgo Networkを作って」といった抽象的な指示に対し、LLMが自律的に重要ノードを特定し、その結果を用いてサブグラフを作成するフローを定義します。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant NetworkXAPI
    participant DB

    User->>LLM: "次数中心性が高い上位2ノードのサブグラフを作って"
    LLM->>Backend: node_get_top_ranked(metric="degree", k=2)
    Backend->>NetworkXAPI: Call MCP Tool: node_get_top_ranked
    NetworkXAPI->>DB: Calculate & Query
    DB-->>NetworkXAPI: Top Nodes List
    NetworkXAPI-->>Backend: [{"node_id": "n1", ...}, {"node_id": "n2", ...}]
    Backend-->>LLM: Top Nodes Data

    LLM->>Backend: subgraph_create_from_nodes(node_ids=["n1", "n2"])
    Backend->>NetworkXAPI: Call MCP Tool: subgraph_create_from_nodes
    NetworkXAPI->>DB: Check if same subgraph exists
    DB-->>NetworkXAPI: Existing ID (if found) or None
    alt Subgraph Exists
        NetworkXAPI-->>Backend: Reuse Existing ID
    else Subgraph Not Exists
        NetworkXAPI->>DB: Create Subgraph Network
        DB-->>NetworkXAPI: New Network ID
        NetworkXAPI-->>Backend: Subgraph Info
    end
    
    note right of Backend: Backend Automatically Updates Chat Context<br/>(chat.network_id = subgraph_id)
    Backend->>DB: Update Chat.network_id
    Backend-->>LLM: Success Message w/ Context Switch Info

    LLM->>Backend: visualization_generate(focus_network_id=...)
    Backend-->>User: Render Update
```

## 6.6. パスサブグラフ作成フロー

**目的:** 「Node A と Node B の最短経路のサブグラフを作って」という指示を、2 つのツールの組み合わせで実現するフローを定義します。

**設計判断: 経路サブグラフの専用 MCP ツールは用意しない。** 最短経路の算出と、ノード列からのサブグラフ作成は、それぞれ独立して有用な操作である。両者を束ねた専用ツールを作ると、「経路は見たいがサブグラフは要らない」場合に使えるものがなくなる。エージェントは 2 ステップを組み立てられるので、ツールの側で束ねる必要がない。

なお、フロントエンドからの直接操作のために REST 側には経路サブグラフの生成が存在する。エージェント経由と直接操作で入口が異なる例である（[3_NetworkXAPI.md](./3_NetworkXAPI.md) 3.6）。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant NetworkXAPI
    participant DB

    User->>LLM: "Node AとNode Bの最短経路のサブグラフを作って"

    LLM->>Backend: analysis_shortest_path(source="A", target="B")
    Backend->>NetworkXAPI: Call MCP Tool: analysis_shortest_path
    NetworkXAPI->>NetworkXAPI: 最短経路を算出
    NetworkXAPI-->>Backend: 経路上のノードID列

    LLM->>Backend: subgraph_create_from_nodes(node_ids=経路上のノード)
    Backend->>NetworkXAPI: Call MCP Tool: subgraph_create_from_nodes
    NetworkXAPI->>DB: サブグラフを作成
    NetworkXAPI-->>Backend: new_network_id を含む結果

    note right of Backend: POST_TOOL フックが new_network_id を検出し、<br/>描画と表示ネットワークの切替を行う
    Backend->>DB: チャットのネットワーク参照を更新

    Backend-->>LLM: 成功メッセージ
    LLM-->>Backend: 最終応答メッセージ
```

## 6.7. ランキングに基づく可視化フロー

**目的:** 「次数が高い上位3ノードを赤くして」といった指示に対し、LLMがランキングルールを構築し、NetworkXAPIがそれを解釈して動的に色を割り当てるフローです。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant NetworkXAPI
    participant DB

    User->>LLM: "次数が高い上位3ノードを赤くして"
    LLM->>Backend: analysis_degree_centrality()
    Backend->>NetworkXAPI: Call MCP Tool: analysis_degree_centrality
    NetworkXAPI->>DB: Save Centrality Values
    NetworkXAPI-->>Backend: Success
    Backend-->>LLM: Success

    Backend-->>LLM: Success

    note right of LLM: Layout calculation must be ensured if not already done
    LLM->>Backend: visualization_generate(node_color_config={scale_type="RANKING", ranking_rules=[{top:3, color:"red"}]})
    Backend->>NetworkXAPI: Call MCP Tool: visualization_generate
    NetworkXAPI->>DB: Fetch Node Values
    NetworkXAPI->>NetworkXAPI: Sort & Apply Colors
    NetworkXAPI-->>Backend: Render Data
    Backend-->>User: Render Update
```

## 6.8. 複合的な可視化フロー (サイズ + オーバーレイ + 個別色指定)

**目的:** 「次数中心性でサイズを決め、上位1人を青、その周辺（サブグラフ）を水色、それ以外をグレーにして」といった複雑な指示を実現するフローです。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant NetworkXAPI
    participant DB

    User->>LLM: "次数中心性でサイズを決め、上位1人を青、その周辺（サブグラフ）を水色、それ以外をグレーにして"
    
    note right of LLM: 1. 次数中心性を計算
    LLM->>Backend: analysis_degree_centrality()
    Backend->>NetworkXAPI: Call MCP Tool: analysis_degree_centrality
    NetworkXAPI-->>Backend: Success
    
    note right of LLM: 2. 上位ノードを特定
    LLM->>Backend: node_get_top_ranked(metric="degree", k=1)
    Backend->>NetworkXAPI: Call MCP Tool: node_get_top_ranked
    NetworkXAPI-->>Backend: [{"node_id": "n1", ...}]
    
    note right of LLM: 3. Ego Networkを作成
    LLM->>Backend: subgraph_ego_network(center="n1", radius=1)
    Backend->>NetworkXAPI: Call MCP Tool: subgraph_ego_network
    NetworkXAPI-->>Backend: subgraph_id (e.g., 999)
    note right of Backend: Context Switch -> 999

    note right of LLM: 4. 複合ルールで可視化生成 (Pattern 2: Contextual Subgraph)
    LLM->>Backend: visualization_generate({<br/>  network_id: 12345,<br/>  focus_network_id: 999,<br/>  node_size_config: {attribute: "degree_centrality"},<br/>  node_label_config: {attribute: "name"},<br/>  context_config: {color: "gray", opacity: 0.3},<br/>  focus_config: {node_color_config: {static_color: "lightblue"}},<br/>  custom_node_colors: [{node_id: "n1", color: "blue"}]<br/>})
    Backend->>NetworkXAPI: Call MCP Tool: visualization_generate
    
    note right of NetworkXAPI: 優先順位に従い色を決定:<br/>1. Custom (Blue)<br/>2. Focus Config (Lightblue)<br/>3. Context Config (Gray)
    NetworkXAPI-->>Backend: Render Data
    Backend-->>User: Render Update
```

## 6.9. 独立したサブグラフ表示フロー

**目的:** 「サブグラフだけを見せて」といった指示に対し、メインの表示対象を親ネットワークからサブグラフ自体（Pattern 3）に切り替えるフローです。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant NetworkXAPI
    participant DB

    User->>LLM: "今のEgo Networkだけを詳しく見たい"
    
    note right of LLM: コンテキストにあるサブグラフIDを特定
    
    note right of LLM: network_id をサブグラフIDに切り替えて可視化を要求 (Pattern 3: Isolated Subgraph)
    LLM->>Backend: visualization_generate({<br/>  network_id: 999, <br/>  focus_network_id: null <br/>})
    Backend->>NetworkXAPI: Call MCP Tool: visualization_generate
    
    note right of Backend: Explicit Network Switch -> 999
    Backend->>DB: Update Chat.network_id

    NetworkXAPI->>DB: Fetch Nodes of Network 999
    NetworkXAPI-->>Backend: Render Data (nodes/links of subgraph only)
    Backend-->>User: Render Update
```

## 6.10. ネットワーク階層ナビゲーションフロー

**目的:** 「全体に戻って」や「親ネットワークに戻って」という指示に対し、コンテキストを上位のネットワークに戻すフローです。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant DB

    User->>LLM: "元のグラフに戻って"
    LLM->>Backend: visualization_switch_network(network_id=Root ID)
    Backend->>NetworkXAPI: Call MCP Tool: visualization_switch_network(network_id)
    
    note right of Backend: Update Context
    Backend->>DB: Chat.network_id = Root ID

    NetworkXAPI->>DB: Fetch Visualization State
    NetworkXAPI-->>Backend: Visualization Data (Main Graph)
    
    Backend-->>User: Render Update (Main Graph)
```

### 6.10.1. 親ネットワークへの切り替え

**目的:** 現在のサブグラフから、一つ上の階層（親ネットワーク）に戻るフローです。

**設計判断: 相対的な移動はバックエンド内のローカルツールが担う。** 「一つ上に戻る」「最初のグラフに戻る」は、移動先の ID をモデルが知っている必要がない操作である。ID を要求すると、モデルは親を調べるための呼び出しを 1 回余分に行うことになり、しかも取り違える余地が生まれる。そのためこれらは NetworkXAPI のツールではなく、バックエンドのプロセス内ツール（`switch_to_parent_network` / `switch_to_main_network`）として提供する。移動先の解決はチャットの状態を持つバックエンドが行う。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant DB

    User->>LLM: "一つ上の階層に戻って"
    LLM->>Backend: switch_to_parent_network()
    note right of Backend: 移動先はバックエンドが解決する
    Backend->>DB: 現在のネットワークの親を取得
    Backend->>DB: チャットのネットワーク参照を親へ更新
    Backend-->>User: Render Update
```

## 6.11. 属性条件によるサブグラフ作成フロー

**目的:** 「20代の女性のサブグラフを作って」といった指示に対し、属性条件を解釈してフィルタリングを実行するフローです。

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant NetworkXAPI
    participant DB

    User->>LLM: "20代の女性のサブグラフを作って"
    
    note right of LLM: 1. 属性を確認
    LLM->>Backend: read_resource(uri="network://.../attributes/nodes")
    Backend->>NetworkXAPI: Call MCP Tool: read_resource
    NetworkXAPI-->>Backend: [Age (float), Gender (string)]
    
    note right of LLM: 2. 条件を構築して実行
    LLM->>Backend: subgraph_create_by_filter(<br/>  conditions=[<br/>    {attribute: "Age", ranges: [{min: 20, max: 29}]},<br/>    {attribute: "Gender", categories: ["Female"]}<br/>  ]<br/>)
    Backend->>NetworkXAPI: Call MCP Tool: subgraph_create_by_filter
    NetworkXAPI->>DB: Query Nodes Matching Conditions (AND/OR Logic)
    NetworkXAPI->>DB: Create Subgraph Network
    NetworkXAPI-->>Backend: Subgraph Info (new_network_id)
    
    note right of Backend: Context Switch -> new_network_id
    Backend->>DB: Update Chat.network_id
    
    Backend-->>LLM: Success
    LLM->>Backend: visualization_generate(network_id={new_network_id})
    Backend-->>User: Render Update
```

## 6.12. Verification First Workflow (安全な可視化フロー)

**目的:** LLMが「存在しない属性」を使用してエラーやハルシネーション（幻覚）を起こすのを防ぐため、計算や可視化の前に必ずデータの存在確認を行うフローです。LLMはシステムプロンプトにより、この手順を遵守するよう強制されています。

```mermaid
sequenceDiagram
    participant LLM
    participant Backend
    participant NetworkXAPI
    
    Note right of LLM: ユーザー: "Degreeで色付けして"

    critical Phase 1: Verification (確認)
        LLM->>Backend: read_resource("network://{id}/attributes/nodes")
        Backend->>NetworkXAPI: Call MCP Tool: read_resource
        NetworkXAPI-->>Backend: { attributes: [{name: "id", ...}] }
        note right of LLM: "degree" がリストにないことを確認
    end

    critical Phase 2: Action (計算)
        LLM->>Backend: analysis_degree_centrality()
        Backend->>NetworkXAPI: Call MCP Tool: analysis_degree_centrality
        NetworkXAPI-->>Backend: Success
    end

    critical Phase 3: Finalization (可視化)
        LLM->>Backend: visualization_generate(node_color_config={attribute: "degree"})
        Backend->>NetworkXAPI: Call MCP Tool: visualization_generate
        NetworkXAPI-->>Backend: Render Data
    end
```

## 6.13. ツール実行ループとコンテキスト切り替え

**目的:** ReAct ループの内部、特に **表示ネットワークの自動切り替え** の仕組みを定義します。

### 6.13.1. 実行ループの構造

ループは 1 イテレーションあたり「生成 → ツール実行 → 結果を履歴へ追加」を行い、最終応答が得られるか上限回数に達するまで繰り返す。

**ループ本体は分岐を持たない。** ツールごとの前処理・後処理・制約は、すべてフックとして登録される（[1_Backend.md](./1_Backend.md) 1.3.3、1.7.1）。以下はいずれもフックであり、エンジンに直書きされているものではない。

| 挙動 | 担当するフックの帯 |
| :--- | :--- |
| 引数に現在のネットワーク ID を補完する | PRE / 正規化 |
| 高コストな計算や存在しない属性を拒否する | PRE / ガード |
| 新しいネットワークが生まれたら表示を切り替えて描画する | POST |
| 可視化データを含む結果を描画する | POST |
| ツールを呼ばずに終わろうとしたターンを継続させる | NO_TOOL_CALLS |

**新しい挙動を追加するときは、フックとして登録する。** ループ本体に条件を書き足してはならない。この制約の根拠は [1_Backend.md](./1_Backend.md) 1.7.1 を参照。

### 6.13.2. サブグラフ作成時の自動コンテキスト切り替え

サブグラフを作成するツールは、描画も表示切替も行わない。**結果に新しいネットワーク ID を含めるだけである。** それを検出して副作用を起こすのは POST フックの役割である。

この分離により、サブグラフを作るツールが何種類あっても、切り替えと描画の実装は 1 箇所で済む。

```mermaid
sequenceDiagram
    participant Engine as ReAct ループ
    participant LLM as LLM
    participant Hook as POST フック
    participant Queue as SSE Queue
    participant MCP as NetworkXAPI
    participant DB as Database

    Note over Engine: ループ開始（現在のネットワーク = 親）

    Engine->>LLM: 会話履歴を送信
    LLM-->>Engine: ツール呼び出し要求: subgraph_largest_component

    Note over Engine: PRE フックが network_id を補完
    Engine->>Queue: SSE送信 "tool_execution" (開始)
    Engine->>MCP: ツール実行
    MCP->>DB: サブグラフを作成・保存
    MCP-->>Engine: 実行結果 { "new_network_id": ... }

    Note over Engine, Hook: ★ POST フックが new_network_id を検出 ★
    Engine->>Hook: POST_TOOL ディスパッチ
    Hook->>DB: チャットのネットワーク参照を更新
    Hook->>MCP: visualization_generate（新しいネットワークに対して）
    MCP-->>Hook: レンダリングデータ
    Hook->>Queue: SSE送信 "render_update"

    Engine->>Queue: SSE送信 "tool_execution" (完了)
    Engine->>Engine: 結果を履歴に追加

    Note over Engine: 次のイテレーション（現在のネットワーク = サブグラフ）

    Engine->>LLM: 会話履歴（結果含む）を送信
    LLM-->>Engine: 最終応答
    Engine->>Queue: SSE送信（終端イベント）
```

**この図が示す最も重要な点**: サブグラフ作成の直後、ユーザーの後続の指示（「それを赤く塗って」）は、明示的な指定なしに新しいサブグラフへ適用される。表示中のネットワークが会話の状態として保持されているためである（[1_Backend.md](./1_Backend.md) 1.4.1）。
