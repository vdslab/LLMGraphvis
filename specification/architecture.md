# アーキテクチャ設計

## 1. C4モデル

### 1.1. コンテキスト図 (Context Diagram)

システム全体の概観を示します。ユーザーがどのようにシステムとやり取りし、どの外部システムと連携するかを表します。

```mermaid
graph TD
    subgraph "LLMGraph-vis"
        A[Web Application]
    end

    U[ユーザー] -- "グラフの可視化・分析" --> A
    A -- "レイアウト推薦・チャット" --> LLM[LLM Services]

    style U fill:#d1e0ff,stroke:#333,stroke-width:2px
    style LLM fill:#ffccd1,stroke:#333,stroke-width:2px
```

| 要素 | 説明 |
|:---|:---|
| **ユーザー** | グラフの可視化や分析を行う研究者や開発者。 |
| **Web Application** | 本システムのコア機能を提供するWebアプリケーション。 |
| **LLM Services** | グラフのレイアウト推薦やチャット機能のために利用する外部の大規模言語モデルサービス。(OpenAI API, Google Geminiなど) |

### 1.2. コンテナ図 (Container Diagram)

アプリケーションを構成する主要なコンテナ（サービス）と、それらの間のデータの流れを示します。

```mermaid
graph TD
    subgraph "Web Browser"
        F[Frontend]
    end

    subgraph "Docker Environment"
        B[API Service]
        N[NetworkX MCP]
        DB[(Database)]
    end

    U[ユーザー] -- "HTTPS" --> F
    F -- "API (HTTPS)" --> B
    B -- "API (HTTP)" --> N
    B -- "PostgreSQL" --> DB
    B -- "API (HTTPS)" --> LLM[LLM Services]

    style F fill:#82b3ff,stroke:#333,stroke-width:2px
    style B fill:#94e2d5,stroke:#333,stroke-width:2px
    style N fill:#f5c2e7,stroke:#333,stroke-width:2px
    style DB fill:#f9e2af,stroke:#333,stroke-width:2px
```

| コンテナ | 説明 | 技術スタック |
|:---|:---|:---|
| **Frontend** | ユーザーインターフェースを提供し、バックエンドと通信するシングルページアプリケーション。 | React, Vite |
| **API Service** | ビジネスロジック、認証、外部API連携を担当するバックエンド。 | FastAPI, Python |
| **NetworkX Model Context Protocol (NetworkXMCP)** | グラフ計算やレイアウト処理に特化した計算サービス。 | FastAPI, NetworkX, Python |
| **Database** | ユーザー情報やセッションデータを永続化するデータベース。 | PostgreSQL |

## 2. コンポーネント図 (Component Diagram)

各コンテナの内部コンポーネントと責務を示します。

### 2.1. APIコンテナ

```mermaid
graph TD
    subgraph "API Container"
        R[Routers]
        S[Services]
        M[Models/Schemas]
        DI[Database Interface]
        AUTH[Auth Logic]
    end

    R -- "ビジネスロジックの呼び出し" --> S
    S -- "データ構造の利用" --> M
    S -- "DB操作" --> DI
    R -- "認証" --> AUTH
    AUTH -- "DB操作" --> DI
```

| コンポーネント | 説明 |
|:---|:---|
| **Routers** | APIエンドポイントを定義し、リクエストを適切なサービスにルーティングする。 |
| **Services** | ビジネスロジックを実装する。LLMサービス連携やNetworkXMCPの呼び出しなど。 |
| **Models/Schemas** | Pydanticモデルとデータベーススキーマを定義する。 |
| **Database Interface** | SQLAlchemyを使用してデータベースとのやり取りを抽象化する。 |
| **Auth Logic** | OAuth2/JSON Web Tokenによるユーザー認証・認可のロジックを実装する。 |

### 2.2. Frontendコンテナ

```mermaid
graph TD
    subgraph "Frontend Container"
        P[Pages]
        C[Components]
        ST[Stores]
        SV[Services]
    end

    P -- "コンポーネントの組み合わせ" --> C
    P -- "状態の参照・更新" --> ST
    C -- "状態の参照・更新" --> ST
    ST -- "API通信" --> SV
```

| コンポーネント | 説明 |
|:---|:---|
| **Pages** | 各画面（ページ）を構成するコンポーネント。 |
| **Components** | ボタンやナビゲーションバーなど、再利用可能なUI部品。 |
| **Stores** | Zustandを使用してアプリケーション全体の状態（ユーザー情報、グラフデータなど）を管理する。 |
| **Services** | APIクライアントなど、外部との通信処理をまとめたモジュール。 |

## 3. データ永続化

本システムにおけるデータの永続化は、以下の2つの仕組みによって実現されています。

- **サーバーサイド (Database)**:
    - **技術**: PostgreSQL
    - **永続化されるデータ**:
        - ユーザーアカウント情報（ハッシュ化されたパスワードを含む）
        - 各ユーザーの会話履歴
        - メッセージ（ユーザーの発言、LLMの応答）
        - GraphMLデータ本体
        - 計算結果のキャッシュ（レイアウト座標、中心性指標など）
    - **役割**: アプリケーションのコアとなるデータを安全に保管し、ユーザーセッションを跨いで状態を維持します。

- **クライアントサイド (Web Browser)**:
    - **技術**: `localStorage`
    - **永続化されるデータ**:
        - 認証用のJSON Web Token (JWT)
    - **役割**: ユーザーがアプリケーションを再訪問した際に、再ログインの手間を省き、シームレスな認証状態を維持します。トークンの有効期限が切れた場合は、再認証が要求されます。

## 4. シーケンス図

### 4.1. レイアウト計算とキャッシュ利用のフロー

ユーザーがレイアウト計算を要求した際の、キャッシュを利用した効率的な処理フローを示します。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant DB as Database
    participant N as NetworkXMCP

    U->>F: レイアウト計算を要求 (例: spring layout)
    F->>B: POST /network/layout (layout_type: "spring")

    B->>DB: "spring"レイアウトのキャッシュがあるか確認
    
    alt キャッシュが存在する場合
        DB-->>B: キャッシュされた座標データを返す
        B-->>F: 計算結果 (キャッシュ)
        F->>U: グラフを再描画
    else キャッシュが存在しない場合
        DB-->>B: キャッシュなし
        B->>N: /tools/change_layout (GraphML, "spring")
        N-->>B: 計算結果 (新しい座標と更新されたGraphML)
        B->>DB: 新しい座標をキャッシュに保存し、更新されたGraphMLも保存
        DB-->>B: 保存成功
        B-->>F: 計算結果 (新規)
        F->>U: グラフを再描画
    end
```

### 4.2. データ永続化のフロー

ユーザー登録、ログイン時のJWT保存、ファイルアップロード時のデータ保存といった、クライアントとサーバー双方でのデータ永続化の流れを示します。

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

### 4.3. チャットによる分析とキャッシュ利用フロー

ユーザーの指示による分析処理において、キャッシュの利用と結果の永続化がどのように行われるかを示します。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant DB as Database
    participant LLM as LLM Service
    participant N as NetworkXMCP

    U->>F: チャットで指示を入力 ("次数中心性を計算して")
    F->>B: POST /chat/process (message)
    B->>DB: ユーザーメッセージを保存

    B->>LLM: ユーザーの指示とツール定義を送信
    LLM-->>B: ツール呼び出しを要求 (calculate_centrality, type:"degree")

    B->>DB: "degree"中心性のキャッシュがあるか確認

    alt キャッシュが存在する場合
        DB-->>B: キャッシュされた中心性データを返す
        B->>LLM: ツール実行結果(キャッシュ)を送信
    else キャッシュが存在しない場合
        DB-->>B: キャッシュなし
        B->>N: /tools/calculate_centrality (GraphML, "degree")
        N-->>B: 計算結果 (新規)
        
        rect rgb(230, 240, 255)
            note over B: 分析結果の永続化
            B->>DB: 新しい中心性データをキャッシュに保存
            B->>DB: (オプション)計算結果をGraphML属性に反映して保存
        end

        B->>LLM: ツール実行結果(新規)を送信
    end

    LLM-->>B: 最終的な応答メッセージを生成
    B->>DB: LLMの応答メッセージを保存

    B-->>F: 最終応答と計算結果(networkUpdate)
    F->>F: チャット履歴とグラフ表示を更新
```

### 4.4. 複数ツール呼び出しによる連続処理フロー

一度の指示で複数の分析や操作が必要な場合の、連続的なツール呼び出しフローを示します。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant DB as Database
    participant LLM as LLM Service
    participant N as NetworkXMCP

    U->>F: 「次数中心性を計算し、上位5ノードを赤色に変えて」
    F->>B: POST /chat/process (message)

    B->>LLM: ユーザーの指示と会話履歴を送信
    LLM-->>B: 1回目のツール呼び出しを要求 (calculate_centrality)

    B->>DB: 中心性キャッシュを確認
    alt キャッシュなし
        B->>N: /tools/calculate_centrality を実行
        N-->>B: 計算結果
        B->>DB: 結果をキャッシュに保存
    else キャッシュあり
        DB-->>B: キャッシュされたデータを返す
    end

    B->>LLM: 1回目のツール実行結果を送信
    LLM-->>B: 2回目のツール呼び出しを要求 (change_node_attributes)
    note right of B: LLMは中心性データから上位5ノードを特定し、<br>次のツールの引数(node_ids, color)を生成する

    B->>B: change_node_attributes を実行
    note right of B: GraphML内のノード属性を直接変更
    B->>DB: 属性が更新されたGraphMLを保存

    B->>LLM: 2回目のツール実行結果を送信
    LLM-->>B: 最終的な応答メッセージを生成

    B->>DB: LLMの応答メッセージを保存
    B-->>F: 最終応答と更新されたグラフ情報
    F->>U: 応答と、ノードが赤色に変化したグラフを表示
```