# 6. 主要な処理フローとデータ生成（最適化版）

**前提知識レベル:**
- シーケンス図の読解能力
- REST APIおよびWebSocketに関する知識
- LLMのFunction Calling（ツール呼び出し）に関する基本的な理解

## 6.1. 概要

このドキュメントでは、主要なユースケースにおけるコンポーネント間の動的なやり取りと、その過程で実行されるデータ生成のフローを定義します。

本システムのコア機能は、ユーザーの自然言語指示をLLMが解釈し、複数のツールを段階的に呼び出すことで、最終的なネットワークの可視化を実現する点にあります。

---

## 6.2. 新規会話開始（ネットワークアップロード）フロー

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
    note over B,F: 現在の設計は同期処理であり、大規模ネットワークでは<br/>タイムアウトの可能性があるため、将来的には<br/>非同期処理（ポーGリング or WebSocket通知）の検討も視野に入れる。

    %% Step 2: Backend saves initial data and requests default layout calculation
    B->>DB: ネットワーク、会話情報を保存
    DB-->>B: 保存成功 (network_id)
    B->>N: POST /tools/change_layout (network_id, name:"spring")
    note over N: デフォルトのSpring Layoutを計算

    %% Step 3: NetworkXMCP computes and saves layout as an attribute
    N->>DB: 計算したノード座標を、`attributes`に定義を、`attribute_values`に値を保存
    DB-->>N: 保存成功
    N-->>B: 実行成功応答
    B-->>F: アップロード成功 (network_id, conversation_id)

    %% Step 4: Frontend navigates and fetches the initial network data
    F->>F: チャットページへ遷移
    F->>B: GET /chat/stream/{conversation_id}
    note right of F: サーバーからの更新通知を受け取るため、<br/>WebSocket接続を確立する
    F->>B: GET /network/{network_id}/visdata
    note left of F: 可視化データを要求
    B->>DB: ネットワーク構造、属性（座標）をクエリ
    DB-->>B: ネットワークデータ、属性データ
    B->>B: レンダリングデータを組み立て
    B-->>F: 200 OK + { nodes, edges }

    %% Step 5: Frontend renders the initial network
    F->>F: Spring Layoutが適用された初期ネットワークを描画
```

---

## 6.3. 対話によるネットワーク操作フロー

**目的:** ユーザーの曖昧な自然言語指示（例:「重要なノードを大きくして」）から、LLMが具体的な「計算」と「可視化」のツール呼び出しを推論し、実行する、本システムのもっとも中心的なフローです。

### 6.3.1. シーケンス図

このフローでは、計算結果をネットワークの属性として保存しておくことで、同じ計算を何度も繰り返すムダを省く仕組みも示されています。また、関連するファンクションコーリングをまとめて実行することで、LLMとBackendの間のやり取りを最小限に抑え、レイテンシとコストを削減しています。

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

    note over F, B: このフローが開始される時点で、クライアントは<br/>既にWebSocket接続を確立済みであるとする。

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

    %% Step 3: Backend asks LLM for the next steps (combined)
    B->>LLM: 属性リストをツール実行結果として送信
    note right of LLM: 「次数中心性」が属性リストにないことを確認し、
    note right of LLM: 次のステップとして属性計算と視覚マッピングを
    note right of LLM: まとめて要求する。
    LLM-->>B: ツール呼び出し要求 (2. calculate_centrality)

    %% Step 4: Backend executes calculate_centrality
    B->>N: POST /tools/calculate_centrality (centrality_type:"degree")
    N->>N: NetworkXで次数中心性を計算
    N->>DB: 計算結果を、`attributes`に定義を、`attribute_values`に値を保存
    DB-->>N: 保存成功
    N-->>B: 実行成功

    %% Step 5: Backend executes apply_metric_to_visual (calculate_centralityの結果を受けて自動実行)
    B->>N: POST /tools/apply_metric_to_visual (metric:"degree_centrality", visual:"node_size")
    N->>DB: `visual_mapping_rules`にマッピング設定を保存または更新
    DB-->>N: 保存成功
    N-->>B: 実行成功

    %% Step 6: Backend sends notification and final response to Frontend
    B-->>F: WebSocketイベント (event: graph_updated)
    note right of F: サーバーからのWebSocketイベントを受け取り、<br/>データ再取得をトリガーする
    B->>LLM: 全ツール実行完了を報告
    LLM-->>B: 最終応答メッセージ（「次数中心性を計算し...」）
    B->>DB: LLMの応答を保存
    B-->>F: 200 OK + { message: LLMからの応答 }

    %% Step 7: Frontend fetches updated data
    F->>B: GET /network/{network_id}/visdata
    B->>DB: ネットワーク構造、全属性、視覚ルールをクエリ
    DB-->>B: 各種データ
    B->>B: レンダリングデータを動的に組み立て
    B-->>F: 200 OK + { nodes, edges }
    F->>F: render(nodes, edges)
```

### 6.3.2. データフローと責務詳細 (LLM Function Calling)

ユーザーが「次数が多いノードを大きくして」のような曖昧な指示を出すと、システムは以下の手順でレンダリングデータを更新します。

#### 1. LLMによる複数ステップのツールプランニング

BackendとLLMは、以下のような複数回のやり取りを通じて、段階的にタスクを実行します。

- **1回目のLLM呼び出し**:
    - **Backend → LLM**: ユーザー指示 `「友達が多い人を大きく表示して」` + ツールリスト
    - **LLM → Backend**: `list_attributes()` の呼び出しを要求

- **2回目のLLM呼び出し**:
    - **Backend → LLM**: `list_attributes` の実行結果 `['weight']`
    - **LLM → Backend**: ツール呼び出しを要求:
      1. `calculate_centrality(type: "degree")`
    - **Backend**: `calculate_centrality` の実行結果を受けて、自動的に `apply_metric_to_visual(metric: "degree_centrality", visual: "node_size", mapping: {scale: 'linear', ...})` を実行

#### 2. Backendによるツール実行と永続化

Backendは、LLMの要求にしたがってNetworkXMCPのAPIを呼び出し、結果を正規化されたテーブルに永続化します。複数のツール呼び出しが要求された場合は、それらを順番に実行します。

- `GET /tools/list_attributes`: `attributes`テーブルから属性名の一覧を取得します。
- `POST /tools/calculate_centrality`: 計算結果の**値**を`attribute_values`系のテーブルに、その**定義**を`attributes`系のテーブルに書き込みます。
- `POST /tools/apply_metric_to_visual`: マッピングルールを`visual_mapping_rules`テーブルに書き込みます。

#### 3. Backendによる動的なレンダリングデータ生成

Frontendが `/network/{network_id}/visdata` を呼び出すと、Backendはリクエストの都度、以下の情報をDBから読み込み、最終的なレンダリングデータを動的に組み立てて返します。

1.  `networks`テーブルから元のネットワーク構造
2.  `attributes`と`attribute_values`テーブルからすべての属性データ（座標を含む）
3.  `visual_mapping_rules`テーブルから適用すべき視覚ルール

Backendは、これらの情報を統合し、各ノード・エッジのスタイルを決定して最終的なJSONを生成します。

---

## 6.4. ツール呼び出し失敗時のエラーハンドリングフロー

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
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality, centrality_type:"pagerank")

    B->>N: /tools/calculate_centrality (network_id, centrality_type:"pagerank")
    note over N: "pagerank" は未実装のためエラーを返す
    N-->>B: 実行失敗の応答 (エラーメッセージ)

    B->>LLM: ツールの実行結果（失敗）を送信
    note right of LLM: LLMは失敗を認識し、<br/>ユーザーへの説明と代替案を生成する。
    LLM-->>B: 最終的な応答メッセージを生成 (例: 「申し訳ありません、PageRankの計算に失敗しました。次数中心性など、他の指標ではいかがでしょうか？」)

    B->>F: 最終応答
    F->>U: ネットワークは変更せず、LLMからのメッセージを表示
```

## 6.5. ファンクションコーリングの最適化に関する注意点

### 6.5.1. 最適化のメリット

1. **レイテンシの削減**:
   - LLMとBackendの間のやり取りが減少するため、全体的な処理時間が短縮される
   - ユーザーの待ち時間が減少し、体験が向上する

2. **コスト削減**:
   - LLMへのAPI呼び出し回数が減少するため、APIコストが削減される
   - とくに大量のユーザーがいる場合、コスト削減効果は大きい

3. **システムの効率化**:
   - 関連する操作（計算と視覚マッピング）をまとめることで、処理の論理的なグループ化が可能になる

### 6.5.2. 実装上の考慮点

1. **複数ツール呼び出しのパース**:
   - LLMからの応答で複数のツール呼び出しが含まれている場合、それらを適切にパースするロジックが必要

2. **エラーハンドリング**:
   - 複数のツール呼び出しの中で一部が失敗した場合の適切なエラーハンドリングが必要
   - 部分的な成功と失敗の状態をLLMに正確に伝える仕組みが重要

3. **依存関係の考慮**:
   - ツール呼び出し間に依存関係がある場合（前のツールの出力が次のツールの入力になる場合など）、その順序を保証する必要がある

## 6.6. その他の最適化可能な箇所

ファンクションコーリングのまとめ以外にも、以下のような最適化ポイントが考えられます：

### 6.6.1. WebSocketを活用したストリーミング最適化

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXMCP

    U->>F: 「コミュニティを検出して色分けして」
    F->>B: POST /chat/process (message, conversation_id)
    
    B->>LLM: ユーザー指示を送信
    
    %% LLMの思考プロセスをストリーミング
    B-->>F: WebSocket (event: thinking_stream, content: "コミュニティ検出には...")
    note right of F: LLMの思考プロセスをリアルタイムで表示
    
    LLM-->>B: ツール呼び出し要求 (detect_communities)
    
    %% ツール実行状況をストリーミング
    B-->>F: WebSocket (event: tool_execution, tool: "detect_communities", status: "started")
    B->>N: POST /tools/detect_communities
    
    %% 長時間実行の場合は進捗状況も通知
    N-->>B: WebSocket (progress: 30%)
    B-->>F: WebSocket (event: tool_execution, tool: "detect_communities", progress: 30%)
    
    N-->>B: 実行成功
    B-->>F: WebSocket (event: tool_execution, tool: "detect_communities", status: "completed")
    
    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終応答
    
    B-->>F: WebSocket (event: message, content: "コミュニティを検出し...")
    B-->>F: WebSocket (event: graph_updated)
    
    F->>B: GET /network/{network_id}/visdata
    B-->>F: 200 OK + { nodes, edges }
    F->>F: render(nodes, edges)
```

### 6.6.2. バッチ処理による複数属性の一括計算

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXMCP
    
    U->>F: 「重要なノードを特定して」
    F->>B: POST /chat/process (message, conversation_id)
    
    B->>LLM: ユーザー指示を送信
    LLM-->>B: ツール呼び出し要求 (calculate_multiple_centralities)
    
    B->>N: POST /tools/calculate_multiple_centralities (types: ["degree", "betweenness", "closeness"])
    note over N: 複数の中心性指標を<br/>一度のAPIコールで計算
    N-->>B: 実行成功
    
    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終応答
    
    B-->>F: 200 OK + { message: LLMからの応答 }
    B-->>F: WebSocket (event: graph_updated)
    
    F->>B: GET /network/{network_id}/visdata
    B-->>F: 200 OK + { nodes, edges }
    F->>F: render(nodes, edges)
```

### 6.6.3. 条件付きファンクションコーリング

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXMCP
    
    U->>F: 「次数中心性でノードを大きくして」
    F->>B: POST /chat/process (message, conversation_id)
    
    B->>LLM: ユーザー指示を送信
    LLM-->>B: 条件付きツール呼び出し要求 (conditional_calculate_and_apply)
    
    B->>N: POST /tools/conditional_calculate_and_apply (metric: "degree_centrality", visual: "node_size")
    note over N: 属性が存在しなければ計算し、<br/>存在すれば直接視覚化に適用
    N-->>B: 実行成功
    
    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終応答
    
    B-->>F: 200 OK + { message: LLMからの応答 }
    B-->>F: WebSocket (event: graph_updated)
    
    F->>B: GET /network/{network_id}/visdata
    B-->>F: 200 OK + { nodes, edges }
    F->>F: render(nodes, edges)
```

これらの追加の最適化ポイントを実装することで、システム全体のパフォーマンスとユーザー体験をさらに向上させることができます。