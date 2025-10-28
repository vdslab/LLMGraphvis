# 3. 主要な処理フロー

このドキュメントでは、主要なユースケースにおけるコンポーネント間の動的なやり取りをシーケンス図で示します。

認証に関するフローは、[認証フロー](./Authentication.md)を参照してください。

## 3.1. 初期グラフ表示フロー

**目的:** ユーザーがGraphMLファイルをアップロードした後、チャットで指示を出す前のデフォルトのグラフ表示処理を定義します。

**方針:** アップロード処理の一環として、非同期または同期的にデフォルトのレイアウト（Spring Layout）を計算し、その結果を初期表示に利用します。

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service (Backend)
    participant N as NetworkXMCP (Tool Service)
    participant DB as Database

    %% Step 1: User uploads a file
    U->>F: GraphMLファイルをアップロード
    F->>B: POST /network/upload (GraphMLデータ)

    %% Step 2: Backend saves initial data and requests default layout calculation
    B->>DB: GraphML、会話、ネットワーク情報を保存
    DB-->>B: 保存成功 (network_id)
    B->>N: POST /tools/change_layout (network_id, name:"spring")
    note over N: デフォルトのSpring Layoutを計算

    %% Step 3: NetworkXMCP computes and saves layout
    N->>DB: 計算したノード座標 (position) を保存
    DB-->>N: 保存成功
    N-->>B: 実行成功応答
    B-->>F: アップロード成功 (network_id, conversation_id)

    %% Step 4: Frontend navigates and fetches the initial graph data
    F->>F: チャットページへ遷移
    F->>B: GET /network/{network_id}/cytoscape
    B->>DB: レンダリングに必要なデータをクエリ (ノード, エッジ, 計算済みのposition)
    DB-->>B: { nodes: [...], edges: [...] }
    B-->>F: 200 OK + { nodes, edges }

    %% Step 5: Frontend renders the initial graph
    F->>F: Spring Layoutが適用された初期グラフを描画
```

## 3.2. 対話によるグラフ操作フロー

**目的:** ユーザーの曖昧な自然言語指示（例:「重要なノードを大きくして」）から、LLMが具体的な「計算」と「可視化」のツール呼び出しを推論し、実行する、本システムの最も中心的なフローです。

このフローでは、計算結果をキャッシュしておくことで、同じ計算を何度も繰り返す無駄を省く仕組みも示されています。

```mermaid
sequenceDiagram
    autonumber
    %% Participants
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service (Backend)
    participant LLM as LLM Service
    participant N as NetworkXMCP (Tool Service)
    participant DB as Database

    %% WebSocket Connection
    F->>B: WebSocket接続要求 (/chat/ws)
    B-->>F: 接続確立

    %% Step 1: User sends a message
    U->>F: 「友達が多い人を大きく表示して」
    F->>B: WebSocketメッセージ送信 (message, conversation_id)
    B->>DB: ユーザーメッセージを保存

    %% Step 2: Backend invokes LLM
    B->>LLM: ユーザーの指示と会話履歴を送信
    note right of LLM: LLMは「友達が多い」を「次数中心性」と解釈し、<br/>「大きく表示」を「ノードサイズ」に割り当てる判断を行う。
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality → apply_metric_to_visual)

    %% Step 3: Backend calls tools
    B->>N: /tools/calculate_centrality (network_id, type:"degree")
    N-->>B: 実行成功
    B->>N: /tools/apply_metric_to_visual (network_id, metric:"degree_centrality", visual:"node_size")
    N-->>B: 実行成功

    %% Step 4: Backend sends a notification via WebSocket
    note right of B: グラフデータが更新されたことを通知する
    B-->>F: WebSocketメッセージ (type: "graph_updated")

    %% Step 5: Frontend fetches the updated graph data via HTTP
    note left of F: 通知を受け、HTTPで最新のグラフデータを取得
    F->>B: GET /network/{network_id}/cytoscape
    B->>DB: レンダリングに必要なデータをクエリ
    DB-->>B: { nodes: [...], edges: [...] }
    B-->>F: 200 OK + { nodes, edges }
    F->>F: render(nodes, edges)

    %% Step 6: Backend gets final response from LLM and sends it via WebSocket
    B->>LLM: 全てのツール実行結果を送信
    LLM-->>B: 最終的な応答メッセージを生成
    B->>DB: LLMの応答メッセージを保存
    B-->>F: WebSocketメッセージ (type: "llm_response", payload: { ... })
    F->>U: LLMからの応答を画面に表示
```

### フローの補足

上のシーケンス図で示された主要なステップに関する詳細情報は、以下のドキュメントで定義されています。

- **APIエンドポイント**
  - `POST /chat/process` をはじめとするBackendのAPIについては、「[2.1. バックエンド仕様](./Backend.md)」を参照してください。
  - `/tools/calculate_centrality` など、Backendから呼び出される計算サービスのAPIは、「[2.3. グラフ計算サービス仕様 (NetworkXMCP)](./NetworkXMCP.md)」で定義されています。

- **データ永続化**
  - 計算結果のキャッシュ(`calculation_results`)など、このフローで利用されるデータベースのスキーマ設計については、「[4. データベーススキーマ仕様](./database-schema.md)」で詳しく解説しています。

- **レンダリングデータ生成**
  - フローの最終段階でBackendがレンダリング用データを組み立てるプロセスと、そのJSONデータの具体的な仕様は、「[LLM Function Callingによるレンダリングデータ生成フロー](./rendering-data-flow.md)」で定義されています。

## 3.3. ツール呼び出し失敗時のエラーハンドリングフロー

**目的:** システムが予期せぬ状況（例: 未実装の計算）に陥った場合でも、LLMが状況を理解し、ユーザーに代替案を提示することで、対話を継続できるようにします。

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXMCP

    U->>F: 「PageRankを計算して」
    F->>B: POST /chat/process (message, conversation_id)

    B->>LLM: ユーザーの指示を送信
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality, type:"pagerank")

    B->>N: /tools/calculate_centrality (network_id, type:"pagerank")
    note over N: "pagerank" は未実装のためエラーを返す
    N-->>B: 実行失敗の応答 (エラーメッセージ)

    B->>LLM: ツールの実行結果（失敗）を送信
    note right of LLM: LLMは失敗を認識し、<br/>ユーザーへの説明と代替案を生成する。
    LLM-->>B: 最終的な応答メッセージを生成 (例: 「申し訳ありません、PageRankの計算に失敗しました。次数中心性など、他の指標ではいかがでしょうか？」)

    B->>F: 最終応答
    F->>U: グラフは変更せず、LLMからのメッセージを表示
```