# 3. 主要な処理フロー

このドキュメントでは、主要なユースケースにおけるコンポーネント間の動的なやり取りをシーケンス図で示します。

認証に関するフローは、[認証フロー](./Authentication.md)を参照してください。

## 3.1. 新規会話開始（グラフアップロード）フロー

**目的:** ユーザーが新しい分析サイクルを開始するために、GraphMLファイルをアップロードして新規会話を作成する処理を定義します。

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
    note over B,F: 現在の設計は同期処理であり、大規模グラフでは<br/>タイムアウトの可能性があるため、将来的には<br/>非同期処理（ポーGリング or WebSocket通知）の検討も視野に入れる。

    %% Step 2: Backend saves initial data and requests default layout calculation
    B->>DB: GraphML、会話、ネットワーク情報を保存
    DB-->>B: 保存成功 (network_id)
    B->>N: POST /tools/change_layout (network_id, name:"spring")
    note over N: デフォルトのSpring Layoutを計算

    %% Step 3: NetworkXMCP computes and saves layout as an attribute
    N->>DB: 計算したノード座標を属性として `attributes` と `attribute_values` に保存
    DB-->>N: 保存成功
    N-->>B: 実行成功応答
    B-->>F: アップロード成功 (network_id, conversation_id)

    %% Step 4: Frontend navigates and fetches the initial graph data
    F->>F: チャットページへ遷移
    F->>B: GET /network/{network_id}/visdata
    note left of F: 可視化データを要求
    B->>DB: グラフ構造、属性（座標）をクエリ
    DB-->>B: グラフデータ、属性データ
    B->>B: レンダリングデータを組み立て
    B-->>F: 200 OK + { nodes, edges }

    %% Step 5: Frontend renders the initial graph
    F->>F: Spring Layoutが適用された初期グラフを描画
```

## 3.2. 対話によるグラフ操作フロー

**目的:** ユーザーの曖昧な自然言語指示（例:「重要なノードを大きくして」）から、LLMが具体的な「計算」と「可視化」のツール呼び出しを推論し、実行する、本システムの最も中心的なフローです。

このフローでは、計算結果をグラフの属性として保存しておくことで、同じ計算を何度も繰り返す無駄を省く仕組みも示されています。

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

    U->>F: 「友達が多い人を大きく表示して」
    F->>B: POST /chat/process (message, conversation_id)
    B->>DB: ユーザーメッセージを保存

    %% Step 1: Backend asks LLM for a plan
    B->>LLM: ユーザー指示、会話履歴、ツールリストを送信
    note right of LLM: ユーザー指示を解釈し、ツール実行計画を立てる。
    LLM-->>B: ツール呼び出し要求 (1. list_attributes)

    %% Step 2: Backend executes list_attributes
    B->>N: GET /tools/list_attributes (network_id)
    N->>DB: `attributes`テーブルから属性名一覧をクエリ
    DB-->>N: 属性リスト
    N-->>B: 属性リスト（例: ['weight', 'component_id']）

    %% Step 3: Backend asks LLM for the next step
    B->>LLM: 属性リストをツール実行結果として送信
    note right of LLM: 「次数中心性」が属性リストにないことを確認し、
    note right of LLM: 次のステップとして属性計算を要求する。
    LLM-->>B: ツール呼び出し要求 (2. calculate_centrality)

    %% Step 4: Backend executes calculate_centrality
    B->>N: POST /tools/calculate_centrality (type:"degree")
    N->>N: NetworkXで次数中心性を計算
    N->>DB: 計算結果を新しい属性として`attributes`と`attribute_values`に保存
    DB-->>N: 保存成功
    N-->>B: 実行成功

    %% Step 5: Backend asks LLM for the final step
    B->>LLM: 計算成功をツール実行結果として送信
    note right of LLM: 属性が用意できたので、それを視覚的な特徴に
    note right of LLM: 割り当てるためのマッピングルール作成を要求する。
    LLM-->>B: ツール呼び出し要求 (3. apply_metric_to_visual)

    %% Step 6: Backend executes apply_metric_to_visual
    B->>N: POST /tools/apply_metric_to_visual (metric:"degree_centrality", visual:"node_size")
    N->>DB: `visual_mapping_rules`にマッピング設定を保存または更新
    DB-->>N: 保存成功
    N-->>B: 実行成功

    %% Step 7: Backend sends notification and final response to Frontend
    B-->>F: SSEイベント (event: graph_updated)
    note right of F: サーバーからのSSEイベントを受け取り、<br/>データ再取得をトリガーする
    B->>LLM: 全ツール実行完了を報告
    LLM-->>B: 最終応答メッセージ（「次数中心性を計算し...」）
    B->>DB: LLMの応答を保存
    B-->>F: 200 OK + { message: LLMからの応答 }

    %% Step 8: Frontend fetches updated data
    F->>B: GET /network/{network_id}/visdata
    B->>DB: グラフ構造、全属性、視覚ルールをクエリ
    DB-->>B: 各種データ
    B->>B: レンダリングデータを動的に組み立て
    B-->>F: 200 OK + { nodes, edges }
    F->>F: render(nodes, edges)
```

### フローの補足

上のシーケンス図で示された主要なステップに関する詳細情報は、以下のドキュメントで定義されています。

- **APIエンドポイント**
  - `POST /chat/process` をはじめとするBackendのAPIについては、「[2.1. バックエンド仕様](./Backend.md)」を参照してください。
  - `/tools/calculate_centrality` など、Backendから呼び出される計算サービスのAPIは、「[2.3. グラフ計算サービス仕様 (NetworkXMCP)](./NetworkXMCP.md)」で定義されています。

- **データ永続化**
  - 属性データ(`attributes`, `attribute_values`)など、このフローで利用されるデータベースのスキーマ設計については、「[4. データベーススキーマ仕様](./database-schema.md)」で詳しく解説しています。

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
    note right of F: ユーザーの指示をバックエンドに送信

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