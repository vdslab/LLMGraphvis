# 3. 主要な処理フロー

このドキュメントでは、主要なユースケースにおけるコンポーネント間の動的なやり取りをシーケンス図で示します。

## 3.1. 認証とデータ永続化フロー

ユーザー登録、ログイン時のJWT保存、ファイルアップロード時のデータ保存の流れです。

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

ユーザーの自然言語指示に対し、LLMが一度の推論で複数のツール呼び出しを生成し、連続して処理を実行するフローです。このフローでは、ツール実行時にキャッシュの利用も考慮されます。

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

    %% Step 1: ユーザー発話を送信 -> フロント -> Backend 保存
    %% 1
    U->>F: 「友達が多い人を大きく表示して」
    F->>B: POST /chat/process (message, conversation_id)
    B->>DB: ユーザーメッセージを保存

    %% Step 2: Backend が LLM にコンテキストを送る
    %% 2
    B->>LLM: ユーザーの指示と会話履歴を送信
    note right of LLM: LLMは「友達が多い」を「次数中心性」と解釈し、
    note right of LLM: 「大きく表示」を「ノードサイズ」に割り当てる判断を行う。
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality → apply_metric_to_visual)
    note right of B: LLMは一回の推論で複数のツール呼び出しを順次返すことがある

    %% Step 3: Backend が NetworkXMCP に中心性計算を要求
    %% 3
    B->>N: /tools/calculate_centrality (network_id, type:"degree")

    %% Step 4: NetworkXMCP はキャッシュを確認し、必要に応じて計算してキャッシュ保存
    %% 4
    N->>DB: キャッシュ有無を確認 (degree centrality)
    alt キャッシュが存在する場合
        DB-->>N: キャッシュ済み中心性データを返す
        N-->>B: 計算結果 (キャッシュ)
    else キャッシュが存在しない場合
        DB-->>N: キャッシュなし
        N->>DB: GraphML 等の原データを読み込み
        DB-->>N: GraphML データ
        note over N: 中心性計算を実行 (例: degree)
        N->>DB: 新しい中心性データをキャッシュに保存
        DB-->>N: 保存成功
        N-->>B: 計算結果 (新規)
    end

    %% Step 5: Backend が NetworkXMCP に対し、計算したメトリクスをどのように可視属性に割り当てるかを要求
    %% 5
    B->>N: /tools/apply_metric_to_visual (network_id, metric:"degree_centrality", visual:"node_size", mapping:{scale:"linear", range:[8,32]})
    note over N: この呼び出しの目的:
    note over N:  - metric の値を visual 属性にマッピングするルール（例: min/max を基にサイズを線形スケーリング）
    note over N:  - 直接ノードの visual 属性 (size,color,opacity 等) を計算して返す
    note over N:  - （実装選択）結果をDBに永続化するか、Backend に返却するかはサービス設計に依存

    %% Step 6: NetworkXMCP の振る舞い（2つの実装モデルを明示）
    %% 6a: N が属性を DB に保存し、Backend は後でクエリしてレンダリングデータを組み立てるモデル
    alt N が DB に可視属性を保存する場合
        N->>DB: ノード毎の visual 属性を保存 (例: size, color)
        DB-->>N: 保存成功
        N-->>B: 実行成功応答 (保存済み参照を含む)
    else N が Backend に属性を返す場合
        N-->>B: 実行結果 (ノードID と visual 属性の配列)
    end

    %% Step 7: Backend がレンダリング用データを組み立ててフロントへ返す（レンダリングデータ作成は Backend の責任）
    %% 7
    note right of B: ここで重要なのは「レンダリング用データの作成は Backend が行う」こと
    alt Backend が DB を参照して組み立てる場合
        B->>DB: レンダリング用データをクエリ（位置, visual 属性, ラベル等）
        DB-->>B: { nodes: [...], edges: [...] }
        B-->>F: 200 OK + { nodes, edges }  %% フロントは受け取り次第描画
    else Backend が N の戻り値を使って直接組み立てる場合
        B-->>F: 200 OK + { nodes: [...with visual attrs...], edges: [...] }
    end
    F->>F: render(nodes, edges)

    %% Step 8: Backend が LLM にツール実行結果を送信し、会話的応答を生成・保存
    %% 8
    B->>LLM: 全てのツール実行結果を送信（オプショナル: 実行ログ/要約）
    LLM-->>B: 最終的な応答メッセージを生成
    B->>DB: LLMの応答メッセージを保存
    B-->>F: 最終応答と更新されたグラフ情報
    F->>U: 応答と、ノードサイズが変化したグラフを表示
```

### データベーススキーマ（モデル A: N が visual 属性を DB に書き込む）

このリファレンスはModel Aを採用する場合の例です。重要な設計方針は「可視化用の属性は計算結果とは別テーブルに保存する」ことです。

例: PostgreSQLでのテーブル定義（参考）

```sql
-- 計算結果のキャッシュ（中心性などの数値）
CREATE TABLE metric_cache (
    id SERIAL PRIMARY KEY,
    network_id UUID NOT NULL,
    node_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,       -- 例: 'degree_centrality'
    value DOUBLE PRECISION NOT NULL,
    computed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    computed_by TEXT,                -- 例: 'NetworkXMCP_v1'
    ttl_seconds INTEGER DEFAULT 3600
);

-- レンダリング用の visual 属性を格納するテーブル（計算結果とは別）
CREATE TABLE visual_attributes (
    id SERIAL PRIMARY KEY,
    network_id UUID NOT NULL,
    node_id TEXT NOT NULL,
    visual_attrs JSONB NOT NULL,     -- 例: {"size": 18, "color": "#4A90E2"}
    source TEXT,                     -- 例: 'NetworkXMCP' または 'backend'
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    version INTEGER DEFAULT 1
);
```

運用上の注意:

- `metric_cache`は計算結果（数値）を保持し、再計算を避けるために利用します。
- `visual_attributes`には描画に必要な属性（size, color, opacity, labelOverride 等）をJSONBとして格納します。
- Backendはレンダリング用データを組み立てる際に`visual_attributes`を参照して`nodes`の`style`/`position`を合成します。
- `visual_attributes`はNetworkXMCPが書き込む（今回のModel A）。NetworkXMCPは計算後に、ノードごとのvisual属性を`visual_attributes`テーブルにupsertします。

サンプル保存データ（`visual_attrs` の例）:

```json
{
  "size": 24,
  "color": "#F5A623",
  "borderColor": "#8A5A00",
  "borderWidth": 1,
  "note": "mapped from degree_centrality"
}
```

## 3.3. ツール呼び出し失敗時のエラーハンドリングフロー

LLMが要求したツールが何らかの理由（例: サポートされていない計算、不正なパラメーター）で失敗した場合のフローです。システムは失敗の事実をLLMに伝え、LLMがユーザーに対して状況を説明し、代替案を提示する機会を与えます。

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
    note right of LLM: LLMは失敗を認識し、
    note right of LLM: ユーザーへの説明と代替案を生成する。
    LLM-->>B: 最終的な応答メッセージを生成 (例: 「申し訳ありません、PageRankの計算に失敗しました。次数中心性など、他の指標ではいかがでしょうか？」)

    B->>F: 最終応答
    F->>U: グラフは変更せず、LLMからのメッセージを表示
```
