# 3. 主要な処理フロー

このドキュメントでは、主要なユースケースにおけるコンポーネント間の動的なやり取りをシーケンス図で示します。

## 3.1. 認証とデータ永続化フロー

ユーザー登録、ログイン時のJWT保存、ファイルアップロード時のデータ保存の流れです。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant LS as Browser Local Storage
    participant B as API Service
    participant DB as Database

    U->>F: 新規登録情報入力
    F->>B: POST /auth/register (username, password)
    B->>DB: ユーザー情報をハッシュ化して保存
    DB-->>B: 保存成功
    B-->>F: 登録完了

    U->>F: ログイン情報入力
    F->>B: POST /auth/token (username, password)
    B->>DB: ユーザー情報検証
    DB-->>B: 検証結果
    B-->>F: JSON Web Token (JWT)
    F->>LS: JWTを保存
    LS-->>F: 保存成功

    U->>F: GraphMLファイルアップロード
    F->>B: POST /network/upload (JWT, GraphML)
    B->>B: JWT検証
    B->>DB: GraphMLデータ、会話情報などを保存
    DB-->>B: 保存成功
    B-->>F: アップロード成功
```

## 3.2. レイアウト計算とキャッシュ利用フロー

キャッシュを利用した効率的なレイアウト計算処理のフローです。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant N as NetworkXMCP
    participant DB as Database

    U->>F: レイアウト計算を要求 (例: spring layout)
    F->>B: POST /network/layout (network_id, layout_type)

    B->>N: /tools/change_layout (network_id, layout_type)
    N->>DB: "spring"レイアウトのキャッシュがあるか確認
    
    alt キャッシュが存在する場合
        DB-->>N: キャッシュされた座標データを返す
        N-->>B: 計算結果 (キャッシュ)
        B-->>F: 計算結果
        F->>U: グラフを再描画
    else キャッシュが存在しない場合
        DB-->>N: キャッシュなし
        note over N: DBからGraphMLを読み込み、計算を実行
        N->>DB: 新しい座標をキャッシュに保存し、更新されたGraphMLも保存
        DB-->>N: 保存成功
        N-->>B: 計算結果 (新規)
        B-->>F: 計算結果
        F->>U: グラフを再描画
    end
```

## 3.3. チャットによる分析とキャッシュ利用フロー

ユーザーの指示による分析処理とキャッシュ利用の流れです。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXMCP
    participant DB as Database

    U->>F: チャットで指示を入力 ("次数中心性を計算して")
    F->>B: POST /chat/process (message, conversation_id)
    B->>DB: ユーザーメッセージを保存

    B->>LLM: ユーザーの指示とツール定義を送信
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality, type:"degree")

    B->>N: /tools/calculate_centrality (network_id, type:"degree")
    N->>DB: "degree"中心性のキャッシュがあるか確認

    alt キャッシュが存在する場合
        DB-->>N: キャッシュされた中心性データを返す
        N-->>B: 計算結果 (キャッシュ)
    else キャッシュが存在しない場合
        DB-->>N: キャッシュなし
        note over N: DBからGraphMLを読み込み、計算を実行
        N->>DB: 新しい中心性データをキャッシュに保存
        DB-->>N: 保存成功
        N-->>B: 計算結果 (新規)
    end

    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終的な応答メッセージを生成
    B->>DB: LLMの応答メッセージを保存

    B-->>F: 最終応答と計算結果(networkUpdate)
    F->>F: チャット履歴とグラフ表示を更新
```

## 3.4. LLMによる複数ツール呼び出しフロー

ユーザーの自然言語指示に対し、LLMが一度の推論で複数のツール呼び出しを生成し、連続して処理を実行するフローです。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXMCP
    participant DB as Database

    U->>F: 「友達が多い人を大きく表示して」
    F->>B: POST /chat/process (message, conversation_id)

    B->>LLM: ユーザーの指示と会話履歴を送信
    note right of LLM: LLMは「友達が多い」を「次数中心性」と解釈し、
    note right of LLM: 「大きく表示」を「ノードサイズ」に割り当てる判断を一度の推論で行う。
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality, apply_metric_to_visual)
    note right of B: LLMは複数のツール呼び出しを一度に生成する

    B->>N: /tools/calculate_centrality (network_id, type:"degree")
    note over N: 計算し、結果をDBにキャッシュ
    N-->>B: 計算成功の応答

    B->>N: /tools/apply_metric_to_visual (network_id, metric:"degree_centrality", visual:"node_size")
    note over N: キャッシュから中心性データを読み込み、
    note over N: ノードサイズを更新したGraphMLを生成してDBに保存
    N-->>B: 実行成功の応答

    B->>LLM: 全てのツール実行結果を送信
    LLM-->>B: 最終的な応答メッセージを生成

    B->>DB: LLMの応答メッセージを保存
    B-->>F: 最終応答と更新されたグラフ情報
    F->>U: 応答と、ノードサイズが変化したグラフを表示
```

## 3.5. チャットによるレイアウト計算フロー

ユーザーの自然言語指示に対し、LLMがレイアウト計算ツールを呼び出し、グラフのレイアウトを更新するフローです。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant LLM as LLM Service
    participant N as NetworkXMCP
    participant DB as Database

    U->>F: チャットで指示を入力 ("springレイアウトを適用して")
    F->>B: POST /chat/process (message, conversation_id)
    B->>DB: ユーザーメッセージを保存

    B->>LLM: ユーザーの指示とツール定義を送信
    LLM-->>B: ツール呼び出しを要求 (change_layout, layout_type:"spring")

    B->>N: /tools/change_layout (network_id, layout_type:"spring")
    N->>DB: "spring"レイアウトのキャッシュがあるか確認

    alt キャッシュが存在する場合
        DB-->>N: キャッシュされた座標データを返す
        N-->>B: 計算結果 (キャッシュ)
    else キャッシュが存在しない場合
        DB-->>N: キャッシュなし
        note over N: DBからGraphMLを読み込み、計算を実行
        N->>DB: 新しい座標をキャッシュに保存し、更新されたGraphMLも保存
        DB-->>N: 保存成功
        N-->>B: 計算結果 (新規)
    end

    B->>LLM: ツール実行結果を送信
    LLM-->>B: 最終的な応答メッセージを生成
    B->>DB: LLMの応答メッセージを保存

    B-->>F: 最終応答と計算結果(networkUpdate)
    F->>F: チャット履歴とグラフ表示を更新
```
