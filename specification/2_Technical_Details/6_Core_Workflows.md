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
    B-XN: POST /tools/initialize_network (network_id, graphml_data)
    note right of B: ネットワークの初期化と<br/>初期レンダリングデータ生成を要求

    %% Step 4: Frontend waits for SSE event
    F->>B: GET /chat/{chat_id}/stream
    note right of F: SSE接続を確立し、<br/>ネットワークの初期化完了を待つ。<br/>この間、ローディング画面などを表示。

    %% Step 5: Background processing in NetworkXAPI
    N->>N: 1. GraphMLを正規化
    N->>DB: 2. ノードとエッジをDBに保存
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
    participant LLM as LLM Service
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
    LLM-->>B: ツール呼び出し要求 (1. list_attributes)

    %% Step 2: Backend executes tools and streams status
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "list_attributes", status: "started" })
    B->>N: GET /tools/list_attributes (network_id)
    N->>DB: 属性テーブル群から属性名一覧をクエリ
    DB-->>N: 属性リスト
    N-->>B: 属性リスト（例: ['weight', 'community_id']）
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "list_attributes", status: "completed" })

    %% Step 3: Backend continues planning with LLM
    B->>LLM: 属性リストをツール実行結果として送信
    LLM-->>B: ツール呼び出し要求 (2. visualize_centrality)

    %% Step 4: Backend executes the combined visualization tool
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "visualize_centrality", status: "started" })
    note right of B: 内部でcalculate_centralityと<br/>generate_visualizationを順次実行
    B->>N: POST /tools/calculate_centrality
    N-->>B: 計算完了
    B->>N: POST /tools/generate_visualization
    N-->>B: 最終レンダリングデータ { nodes: [...], links: [...] }
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "visualize_centrality", status: "completed" })

    %% Step 5: Backend sends final data and text response via SSE
    B-->>F: SSEイベント (event: render_update, data: { nodes, links })
    note right of F: グラフの更新データを受け取り、<br/>即座に画面を再描画する。

    B->>LLM: ツール実行完了を報告
    LLM-->>B: 最終応答メッセージ（「次数中心性を計算し...」）
    B->>DB: LLMの応答を保存
    B-->>F: SSEイベント (event: message, data: { role: "assistant", content: "次数中心性を計算し..." })
    note right of F: テキスト応答を受け取り、<br/>チャット履歴に追加する。

    %% Step 6: Frontend renders the updated network
    F->>F: render(event.data.nodes, event.data.links)
```

### 6.3.2. データフローと責務詳細

この統一フローにおいて、フロントエンドは`POST /chat/{id}/process`を呼び出した後、HTTPレスポンスを待つことなく、即座に操作可能な状態を維持します。ローディング状態の管理は、SSEから送られてくる`tool_execution`イベントの`status`（`started`/`completed`）に基づいて行います。

1.  **リクエストの即時受付**:
    - Backendは`POST /chat/{id}/process`のリクエストを受け取ると、メッセージをDBに保存し、即座に`202 Accepted`を返す。これにより、フロントエンドはブロックされない。

2.  **LLMによるプランニングとツールの実行**:
    - BackendはバックグラウンドでLLMとの対話を開始する。
    - LLMの思考プロセスや、`list_attributes`、`visualize_centrality`といったツールの実行状況は、`thinking_stream`や`tool_execution`といった専用のSSEイベントを通じて逐一フロントエンドに通知される。

3.  **最終的な結果の通知**:
    - `visualize_centrality`が完了すると、Backendは2つの重要な情報をSSEで送信する。
        1.  `render_update`イベント: NetworkXAPIが生成した最終的なレンダリングデータ（`{nodes, links}`）を送信する。フロントエンドはこれを受けてグラフを再描画する。
        2.  `message`イベント: LLMが生成した最終的なテキスト応答（例：「次数中心性を計算し、ノードのサイズに反映しました。」）を送信する。フロントエンドはこれを受けてチャット履歴を更新する。

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
    LLM-->>B: ツール呼び出しを要求 (visualize_centrality, centrality_type:"pagerank")

    B-->>F: SSEイベント (event: tool_execution, data: { tool: "visualize_centrality", status: "started" })
    B->>N: /tools/calculate_centrality (network_id, centrality_type:"pagerank")
    note over N: "pagerank" は未実装のためエラーを返す
    N-->>B: 実行失敗の応答 (エラーメッセージ)
    B-->>F: SSEイベント (event: tool_execution, data: { tool: "visualize_centrality", status: "failed", error: "..." })

    B->>LLM: ツールの実行結果（失敗）を送信
    note right of LLM: LLMは失敗を認識し、<br/>ユーザーへの説明と代替案を生成する。
    LLM-->>B: 最終的な応答メッセージを生成 (例: 「申し訳ありません、PageRankの計算に失敗しました。次数中心性など、他の指標ではいかがでしょうか？」)

    B-->>F: SSEイベント (event: message, data: { role: "assistant", content: "申し訳ありません..." })
    note right of F: グラフは変更せず、LLMからのエラーメッセージをチャット履歴に表示する。
```