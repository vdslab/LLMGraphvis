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
    participant N as NetworkXAPI (REST API)
    participant DB as Database

    %% Step 1: User uploads a file
    U->>F: GraphMLファイルをアップロード
    F->>B: POST /network/upload (GraphMLデータ)
    note over B,F: 現在の設計は同期処理であり、大規模ネットワークでは<br/>タイムアウトの可能性があるため、将来的には<br/>非同期処理（ポーリング or WebSocket通知）の検討も視野に入れる。

    %% Step 2: Backend saves initial data and requests default layout calculation
    B->>DB: ネットワーク、会話情報を保存
    DB-->>B: 保存成功 (network_id)
    B->>N: POST /tools/change_layout (network_id, name:"spring")

    %% Step 3: NetworkXAPI computes and saves layout as an attribute
    note over N,DB: 'x', 'y'の属性定義を作成後、<br/>各ノードの座標値を定義IDと紐付けて保存
    N->>DB: 1. 'x', 'y'の属性定義を保存
    N->>DB: 2. 各ノードの座標値を保存
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

**目的:** ユーザーの曖昧な自然言語指示（例:「重要なノードを大きくして」）から、LLMが単一の強力なツール呼び出しを計画し、最終的な可視化を一度に実現する、新しいアーキテクチャの中心的なフローです。

### 6.3.1. シーケンス図（新アーキテクチャ）

このフローでは、LLMが視覚化の全体像を一度に計画し、`NetworkXAPI`がそれを実行します。状態（視覚ルール）は永続化されず、毎回動的に生成されます。

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

    note over F, B: このフローが開始される時点で、クライアントは<br/>既にWebSocket接続を確立済みであるとする。

    U->>F: 「友達が多い人を大きく表示して」
    F->>B: POST /chat/process (message, conversation_id)
    B->>DB: ユーザーメッセージを保存

    %% Step 1: Backend asks LLM for a plan
    B->>LLM: ユーザー指示、会話履歴、ツールリストを送信
    note right of LLM: ユーザー指示を解釈し、<br/>可視化の全体計画を立てる。
    LLM-->>B: ツール呼び出し要求 (1. list_attributes)

    %% Step 2: Backend executes list_attributes to aid LLM's planning
    B->>N: GET /tools/list_attributes (network_id)
    N->>DB: 属性テーブル群から属性名一覧をクエリ
    DB-->>N: 属性リスト
    N-->>B: 属性リスト（例: ['weight', 'community_id']）

    %% Step 3: Backend asks LLM for the final visualization plan
    B->>LLM: 属性リストをツール実行結果として送信
    note right of LLM: 「次数中心性」が属性リストにないことを確認。<br/>したがって、計算も実行する必要があると判断。<br/>レイアウト、ノードサイズ、カラーの割り当てを<br/>すべて定義した単一のツールコールを計画する。
    LLM-->>B: ツール呼び出し要求 (2. generate_visualization)

    %% Step 4: Backend executes the single visualization tool
    B->>N: POST /tools/generate_visualization (詳細なJSONパラメータ)
    note over N,DB: リクエストに基づき、属性計算、レイアウト計算、<br/>視覚マッピングをすべて実行し、最終レンダリングデータを生成する。<br>内部では、まず属性名をIDに解決し、そのIDで値を取得する。
    N->>DB: 1. 属性名をIDに解決
    N->>DB: 2. IDを使い属性値を取得
    N-->>B: 最終レンダリングデータ { nodes: [...], links: [...] }

    %% Step 5: Backend sends final data and response to Frontend
    B-->>F: WebSocketイベント (event: render_update, data: { nodes, links })
    note right of F: サーバーからのWebSocketイベントを受け取り、<br/>ペイロード内のデータで直接画面を更新する。<br/>もはや再取得は不要。
    B->>LLM: ツール実行完了を報告
    LLM-->>B: 最終応答メッセージ（「次数中心性を計算し...」）
    B->>DB: LLMの応答を保存
    B-->>F: 200 OK + { message: LLMからの応答 }

    %% Step 6: Frontend renders the updated network
    F->>F: render(event.data.nodes, event.data.links)
```

### 6.3.2. データフローと責務詳細 (LLM Function Calling)

ユーザーが「次数が多いノードを大きくして」のような曖昧な指示を出すと、システムは以下の手順でレンダリングデータを更新します。

#### 1. LLMによるワンショットでのツールプランニング

BackendとLLMは、より少ないやり取りで、より包括的なタスクを実行します。

- **1回目のLLM呼び出し**:
    - **Backend → LLM**: ユーザー指示 `「友達が多い人を大きく表示して」` + ツールリスト
    - **LLM → Backend**: `list_attributes()` の呼び出しを要求（現状把握のため）

- **2回目のLLM呼び出し**:
    - **Backend → LLM**: `list_attributes` の実行結果 `['weight']`
    - **LLM → Backend**: `generate_visualization` の呼び出しを要求。この際、リクエストボディには以下のような**完全な計画**が含まれる。
      - `layout_config`: 使用するレイアウト（例: "spring"）
      - `node_size_config`: `degree_centrality`（存在しないため計算が必要と判断）を`LINEAR`スケールでノードサイズに割り当てる設定
      - `node_color_config`: デフォルトの単色設定

#### 2. NetworkXAPIによるレンダリングデータ生成

Backendは、LLMの計画に従ってNetworkXAPIの`POST /tools/generate_visualization`を一度だけ呼び出します。NetworkXAPIは、このリクエストを受け取ると、内部で以下の処理をすべて実行します。

1.  **属性の確認と計算**:
    - リクエストされた属性（例: `degree_centrality`）がデータベースに存在するか確認します。
    - 存在しない場合は、`NetworkX`ライブラリを用いてその場で計算し、結果をデータベースに永続化します。

2.  **レイアウト計算**:
    - リクエストされたレイアウト（例: `spring`）を計算します。

3.  **マッピングとスタイル計算**:
    - すべてのノードとエッジをループ処理し、リクエストされたルール（サイズ、色など）に基づいて各要素の最終的な視覚スタイル（具体的なピクセルサイズや色コード）を決定します。

4.  **最終データ生成**:
    - フロントエンドが直接描画できる形式（`{ "nodes": [...], "links": [...] }`）のJSONを組み立てて、Backendに返します。

#### 3. Backendによる結果の中継

Backendは、NetworkXAPIから受け取った最終レンダリングデータを、そのままWebSocketを通じてフロントエンドに送信します。フロントエンドは、このデータを使って即座に可視化を更新します。このフローでは、フロントエンドがデータを再取得するための追加のAPI呼び出しは不要です。

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
    participant N as NetworkXAPI

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
    participant N as NetworkXAPI

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
    
    N-->>B: 実行成功 (with final rendering data)
    B-->>F: WebSocket (event: tool_execution, tool: "detect_communities", status: "completed")
    
    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終応答
    
    B-->>F: WebSocket (event: message, content: "コミュニティを検出し...")
    B-->>F: WebSocket (event: render_update, data: { nodes, links })
    
    F->>F: render(event.data.nodes, event.data.links)
```

### 6.6.2. バッチ処理による複数属性の一括計算

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXAPI
    
    U->>F: 「重要なノードを特定して」
    F->>B: POST /chat/process (message, conversation_id)
    
    B->>LLM: ユーザー指示を送信
    LLM-->>B: ツール呼び出し要求 (calculate_multiple_centralities)
    
    B->>N: POST /tools/calculate_multiple_centralities (types: ["degree", "betweenness", "closeness"])
    note over N: 複数の中心性指標を<br/>一度のAPIコールで計算
    N-->>B: 実行成功 (with final rendering data)
    
    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終応答
    
    B-->>F: WebSocket (event: render_update, data: { nodes, links })
    B-->>F: 200 OK + { message: LLMからの応答 }
    
    F->>F: render(event.data.nodes, event.data.links)
```

### 6.6.3. 条件付きファンクションコーリング

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXAPI
    
    U->>F: 「次数中心性でノードを大きくして」
    F->>B: POST /chat/process (message, conversation_id)
    
    B->>LLM: ユーザー指示を送信
    LLM-->>B: 条件付きツール呼び出し要求 (conditional_calculate_and_apply)
    
    B->>N: POST /tools/conditional_calculate_and_apply (metric: "degree_centrality", visual: "node_size")
    note over N: 属性が存在しなければ計算し、<br/>存在すれば直接視覚化に適用
    N-->>B: 実行成功 (with final rendering data)
    
    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終応答
    
    B-->>F: WebSocket (event: render_update, data: { nodes, links })
    B-->>F: 200 OK + { message: LLMからの応答 }
    
    F->>F: render(event.data.nodes, event.data.links)
```

これらの追加の最適化ポイントを実装することで、システム全体のパフォーマンスとユーザー体験をさらに向上させることができます。