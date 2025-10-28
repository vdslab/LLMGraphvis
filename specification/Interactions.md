# 3. 主要な処理フロー

このドキュメントでは、主要なユースケースにおけるコンポーネント間の動的なやり取りをシーケンス図で示します。

## 3.1. 認証とデータ永続化フロー

**目的:** ユーザーが安全にシステムを利用し、作業内容（グラフデータなど）を保存できるようにするための基本的なフローです。

ユーザー登録、ログイン、ファイルアップロード時のやり取りを示します。

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant LS as Browser Local Storage
    participant B as API Service
    participant DB as Database

    U->>F: 新規登録情報入力
    F->>B: POST /auth/register (username, password)
    B->>DB: ユーザー情報をハッシュ化して保存
    DB-->>B: ユーザー登録結果
    B-->>F: 登録完了

    U->>F: ログイン情報入力
    F->>B: POST /auth/token (username, password)
    B->>DB: ユーザー情報検証
    DB-->>B: 検証結果 (ユーザー情報)
    B->>B: JWTを生成
    B-->>F: JSON Web Token (JWT)
    F->>LS: JWTを保存
    LS-->>F: 保存成功

    U->>F: GraphMLファイルアップロード
    F->>B: POST /network/upload (JWT, GraphML)
    B->>B: JWTを検証
    B->>DB: GraphMLデータ、会話情報などを保存
    DB-->>B: 保存成功
    B-->>F: アップロード成功
```

## 3.2. LLMによる複数ツール呼び出しとキャッシュ利用フロー

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

    %% Step 1: User sends a message
    U->>F: 「友達が多い人を大きく表示して」
    F->>B: POST /chat/process (message, conversation_id)
    B->>DB: ユーザーメッセージを保存

    %% Step 2: Backend invokes LLM
    B->>LLM: ユーザーの指示と会話履歴を送信
    note right of LLM: LLMは「友達が多い」を「次数中心性」と解釈し、<br/>「大きく表示」を「ノードサイズ」に割り当てる判断を行う。
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality → apply_metric_to_visual)
    note right of B: LLMは一度の推論で複数のツール呼び出しを順次返すことがある

    %% Step 3: Backend calls the first tool: calculation
    B->>N: /tools/calculate_centrality (network_id, type:"degree")

    %% Step 4: NetworkXMCP checks cache, computes if needed, and saves to cache
    N->>DB: キャッシュ有無を確認 (degree centrality)
    alt キャッシュが存在する場合
        DB-->>N: キャッシュ済み中心性データを返す
        N-->>B: 計算結果 (キャッシュ)
    else キャッシュが存在しない場合
        DB-->>N: キャッシュなし
        N->>DB: GraphML等の原データを読み込み
        DB-->>N: GraphML データ
        note over N: 中心性計算を実行 (例: degree)
        N->>DB: 新しい中心性データをキャッシュに保存
        DB-->>N: 保存成功
        N-->>B: 計算結果 (新規)
    end

    %% Step 5: Backend calls the second tool: visualization mapping
    B->>N: /tools/apply_metric_to_visual (network_id, metric:"degree_centrality", visual:"node_size", mapping:{scale:"linear", range:[8,32]})
    note over N: このツールの目的は、計算された指標（metric）を<br/>具体的な見た目（visual）に変換すること。

    %% Step 6: NetworkXMCP's behavior (implementation choice)
    alt 推奨モデル: NetworkXMCPが可視化属性をDBに保存
        N->>DB: ノード毎のvisual属性を保存 (例: size, color)
        DB-->>N: 保存成功
        N-->>B: 実行成功応答
    else 代替モデル: NetworkXMCPが属性を直接Backendに返す
        N-->>B: 実行結果 (ノードIDとvisual属性の配列)
    end

    %% Step 7: Backend assembles rendering data and returns to Frontend
    note right of B: 重要な設計: レンダリング用データの最終的な組み立ては<br/>Backendの責務である。
    B->>DB: レンダリング用データをクエリ（位置, visual属性, ラベル等）
    DB-->>B: { nodes: [...], edges: [...] }
    B-->>F: 200 OK + { nodes, edges }
    F->>F: render(nodes, edges)

    %% Step 8: Backend informs LLM of tool results and gets final response
    B->>LLM: 全てのツール実行結果を送信
    LLM-->>B: 最終的な応答メッセージを生成
    B->>DB: LLMの応答メッセージを保存
    B-->>F: 最終応答と更新されたグラフ情報
    F->>U: 応答と、ノードサイズが変化したグラフを表示
```

### データベーススキーマ

計算結果のキャッシュや可視化属性の永続化に使用されるデータベーススキーマの詳細は、新しく作成された[データベーススキーマ仕様](./database-schema.md)を参照してください。このドキュメントで、`calculation_results`テーブルなどの設計方針と具体的な構造を定義しています。

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