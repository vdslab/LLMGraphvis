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

**方針:** ネットワークデータの処理は時間がかかる可能性があるため、**非同期処理**を維持します。Backendはアップロードリクエストを即座に受け付け、バックグラウンドでNetworkXAPIを呼び出します。NetworkXAPIは、データのパース、DBへの保存、初期レイアウト計算、デフォルトスタイル適用済みのレンダリングデータ生成までを一貫して行い、完了後にBackend経由でSSEを通じてクライアントに通知します。

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service (Backend)
    participant N as NetworkXAPI (REST API)
    participant DB as Database

    %% Step 1: User creates a new chat
    U->>F: 「新規チャット」ボタンをクリック
    F->>B: POST /chat (body: { "name": "新しいチャット" })
    B->>DB: 1. 新しい`chats`レコードを作成
    DB-->>B: chat_id
    B->>DB: 2. `chats`に紐づく空の`networks`レコードを作成
    DB-->>B: network_id
    B-->>F: 201 Created (chat_id, network_id)

    %% Step 2: Frontend navigates and user uploads a file
    F->>F: チャットページ(`/chat/{chat_id}`)へ遷移
    note right of F: ファイルアップロードUIを表示
    U->>F: GraphMLファイルをアップロード
    F->>B: POST /chat/{chat_id}/upload (GraphMLデータ)

    %% Step 3: Backend accepts the request and starts background task
    B-->>F: 202 Accepted
    note right of B: FastAPIのBackgroundTasksを使い、<br/>後続の重い処理をバックグラウンドで実行
    B->>N: POST /tools/initialize_network (network_id, graphml_data)
    note right of B: ネットワークの初期化と<br/>初期レンダリングデータ生成を要求

    %% Step 4: Frontend waits for SSE event
    F->>B: GET /chat/{chat_id}/stream
    note right of F: SSE接続を確立し、<br/>ネットワークの初期化完了を待つ。<br/>この間、ローディング画面などを表示。

    %% Step 5: Background processing in NetworkXAPI
    N->>N: 1. GraphMLを正規化<br/>(属性型の推論とdata_typeの決定)
    N->>DB: 2. ノードとエッジをDBに保存<br/>(値は型別のテーブルへ)
    DB-->>N: 保存成功
    N->>N: 3. 初期レイアウト(Spring)を計算
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
    participant LLM as LLM Service (Gemini 2.5 Flash)
    participant N as NetworkXAPI (REST API)
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
    LLM-->>B: ツール呼び出し要求 (1. list_node_attributes)

    %% Step 2: Backend executes tools and streams status
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "list_node_attributes", status: "started" })
    B->>N: GET /tools/list_node_attributes (network_id)
    N->>DB: 属性テーブル群から属性名一覧をクエリ
    DB-->>N: 属性リスト
    N-->>B: 属性リスト（例: ['weight', 'community_id']）
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "list_node_attributes", status: "completed" })

    %% Step 3: Backend continues planning with LLM
    B->>LLM: 属性リストをツール実行結果として送信
    LLM-->>B: ツール呼び出し要求 (2. calculate_centrality)

    %% Step 4: Backend executes calculate_centrality
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "calculate_centrality", status: "started" })
    B->>N: POST /tools/calculate_centrality
    N-->>B: 計算完了
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "calculate_centrality", status: "completed" })
    
    B->>LLM: ツール実行結果（成功）を送信
    LLM-->>B: ツール呼び出し要求 (3. list_node_attributes)

    %% Step 5: Backend executes list_node_attributes (Verification)
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "list_node_attributes", status: "started" })
    B->>N: GET /tools/list_node_attributes
    N-->>B: 更新された属性リスト
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "list_node_attributes", status: "completed" })

    B->>LLM: ツール実行結果（成功）を送信
    LLM-->>B: ツール呼び出し要求 (4. generate_visualization)

    %% Step 6: Backend executes generate_visualization
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "generate_visualization", status: "started" })
    B->>N: POST /tools/generate_visualization
    N-->>B: 最終レンダリングデータ { nodes: [...], links: [...] }
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "generate_visualization", status: "completed" })

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
    - BackendはバックグラウンドでLLMとの対話を開始する。
    - LLMの思考プロセスや、`list_node_attributes`、`calculate_centrality`、`calculate_layout`、`generate_visualization`といったツールの実行状況は、`thinking_stream`や`tool_execution`といった専用のSSEイベントを通じて逐一フロントエンドに通知される。
    - **重要**: LLMは計算を実行した後、必ず再度`list_node_attributes`を呼び出して、新しい属性が利用可能になったことを確認してから`generate_visualization`を呼び出す。また、**「name」や「label」などの属性が存在する場合、それを識別可能なラベルとして自動的に選択する。**

3.  **最終的な結果の通知**:
    - `generate_visualization`が完了すると、Backendは2つの重要な情報をSSEで送信する。
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

    U->>F: 「PageRankを計算して」
    F->>B: POST /chat/{id}/process (message)
    B-->>F: 202 Accepted

    B->>LLM: ユーザーの指示を送信
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality, centrality_type:"pagerank")

    B-->>F: SSEイベント (event: tool_execution, data: { tool: "calculate_centrality", status: "started" })
    B->>N: /tools/calculate_centrality (network_id, centrality_type:"pagerank")
    note over N: "pagerank" は未実装のためエラーを返す
    N-->>B: 実行失敗の応答 (エラーメッセージ)
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "calculate_centrality", status: "failed", error: "..." })

    B->>LLM: ツールの実行結果（失敗）を送信
    note right of LLM: LLMは失敗を認識し、<br/>ユーザーへの説明と代替案を生成する。
    LLM-->>B: 最終的な応答メッセージを生成 (例: 「申し訳ありません、PageRankの計算に失敗しました。次数中心性など、他の指標ではいかがでしょうか？」)

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
    LLM->>Backend: get_top_nodes(metric="degree", k=2)
    Backend->>NetworkXAPI: POST /tools/get_top_nodes
    NetworkXAPI->>DB: Calculate & Query
    DB-->>NetworkXAPI: Top Nodes List
    NetworkXAPI-->>Backend: [{"node_id": "n1", ...}, {"node_id": "n2", ...}]
    Backend-->>LLM: Top Nodes Data

    LLM->>Backend: create_subgraph_from_nodes(node_ids=["n1", "n2"])
    Backend->>NetworkXAPI: POST /tools/create_subgraph_from_nodes
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

    LLM->>Backend: generate_visualization(focus_network_id=...)
    Backend-->>User: Render Update
```

## 6.6. パスサブグラフ作成フロー

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Backend
    participant NetworkXAPI
    participant DB

    User->>LLM: "Node AとNode Bの最短経路のサブグラフを作って"
    LLM->>Backend: create_path_subgraph(source="A", target="B")
    Backend->>NetworkXAPI: POST /tools/create_path_subgraph
    NetworkXAPI->>NetworkXAPI: Calculate Shortest Path
    NetworkXAPI->>DB: Create Subgraph
    NetworkXAPI-->>Backend: Subgraph Info

    note right of Backend: Backend Automatically Updates Chat Context
    Backend->>DB: Update Chat.network_id
    
    Backend-->>LLM: Success Message
    LLM-->>B: 最終応答メッセージ
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
    LLM->>Backend: calculate_centrality(type="degree")
    Backend->>NetworkXAPI: POST /tools/calculate_centrality
    NetworkXAPI->>DB: Save Centrality Values
    NetworkXAPI-->>Backend: Success
    Backend-->>LLM: Success

    LLM->>Backend: generate_visualization(node_color_config={scale_type="RANKING", ranking_rules=[{top:3, color:"red"}]})
    Backend->>NetworkXAPI: POST /tools/generate_visualization
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
    LLM->>Backend: calculate_centrality(type="degree")
    Backend->>NetworkXAPI: POST /tools/calculate_centrality
    NetworkXAPI-->>Backend: Success
    
    note right of LLM: 2. 上位ノードを特定
    LLM->>Backend: get_top_nodes(metric="degree", k=1)
    Backend->>NetworkXAPI: POST /tools/get_top_nodes
    NetworkXAPI-->>Backend: [{"node_id": "n1", ...}]
    
    note right of LLM: 3. Ego Networkを作成
    LLM->>Backend: create_ego_network(center="n1", radius=1)
    Backend->>NetworkXAPI: POST /tools/create_ego_network
    NetworkXAPI-->>Backend: subgraph_id (e.g., 999)
    note right of Backend: Context Switch -> 999

    note right of LLM: 4. 複合ルールで可視化生成 (Pattern 2: Contextual Subgraph)
    LLM->>Backend: generate_visualization({<br/>  network_id: 12345,<br/>  focus_network_id: 999,<br/>  node_size_config: {attribute: "degree_centrality"},<br/>  node_label_config: {attribute: "name"},<br/>  context_config: {color: "gray", opacity: 0.3},<br/>  focus_config: {node_color_config: {static_color: "lightblue"}},<br/>  custom_node_colors: [{node_id: "n1", color: "blue"}]<br/>})
    Backend->>NetworkXAPI: POST /tools/generate_visualization
    
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
    LLM->>Backend: generate_visualization({<br/>  network_id: 999, <br/>  focus_network_id: null <br/>})
    Backend->>NetworkXAPI: POST /tools/generate_visualization
    
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
    LLM->>Backend: switch_to_main_network()
    
    Backend->>DB: Get current Chat.network_id
    DB-->>Backend: Current ID (Subgraph)
    Backend->>DB: Find root network ID
    DB-->>Backend: Root ID (Main Graph)
    
    note right of Backend: Update Context Case
    Backend->>DB: Chat.network_id = Root ID
    
    Backend-->>LLM: Success Message (Switched to Main ID)
    
    note right of LLM: Visualize the main network
    LLM->>Backend: generate_visualization(network_id=Root ID)
    Backend-->>User: Render Update (Main Graph)
```