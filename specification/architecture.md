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
    A -- "レイアウト推薦・チャット" --> OAI[OpenAI API]

    style U fill:#d1e0ff,stroke:#333,stroke-width:2px
    style OAI fill:#ffccd1,stroke:#333,stroke-width:2px
```

| 要素 | 説明 |
|:---|:---|
| **ユーザー** | グラフの可視化や分析を行う研究者や開発者。 |
| **Web Application** | 本システムのコア機能を提供するWebアプリケーション。 |
| **OpenAI API** | グラフのレイアウト推薦やチャット機能のために利用する外部のLLMサービス。 |

### 1.2. コンテナ図 (Container Diagram)

アプリケーションを構成する主要なコンテナ（サービス）と、それらの間のデータの流れを示します。

```mermaid
graph TD
    subgraph "Web Browser"
        F[Frontend]
    end

    subgraph "Docker Environment"
        B[API]
        N[NetworkXMCP]
        DB[(Database)]
    end

    U[ユーザー] -- "HTTPS" --> F
    F -- "API (HTTPS)" --> B
    B -- "API (HTTP)" --> N
    B -- "PostgreSQL" --> DB
    B -- "API (HTTPS)" --> OAI[OpenAI API]

    style F fill:#82b3ff,stroke:#333,stroke-width:2px
    style B fill:#94e2d5,stroke:#333,stroke-width:2px
    style N fill:#f5c2e7,stroke:#333,stroke-width:2px
    style DB fill:#f9e2af,stroke:#333,stroke-width:2px
```

| コンテナ | 説明 | 技術スタック |
|:---|:---|:---|
| **Frontend** | ユーザーインターフェースを提供し、バックエンドと通信するSPA。 | React, Vite |
| **API** | ビジネスロジック、認証、外部API連携を担当するバックエンド。 | FastAPI, Python |
| **NetworkXMCP** | グラフ計算やレイアウト処理に特化した計算サービス。 | FastAPI, NetworkX, Python |
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
        D[Database I/F]
        AUTH[Auth Logic]
    end

    R -- "ビジネスロジックの呼び出し" --> S
    S -- "データ構造の利用" --> M
    S -- "DB操作" --> D
    R -- "認証" --> AUTH
    AUTH -- "DB操作" --> D
```

| コンポーネント | 説明 |
|:---|:---|
| **Routers** | APIエンドポイントを定義し、リクエストを適切なサービスにルーティングする。 |
| **Services** | ビジネスロジックを実装する。ChatGPT連携やNetworkXMCPの呼び出しなど。 |
| **Models/Schemas** | Pydanticモデルとデータベーススキーマを定義する。 |
| **Database I/F** | SQLAlchemyを使用してデータベースとのやり取りを抽象化する。 |
| **Auth Logic** | OAuth2/JWTによるユーザー認証・認可のロジックを実装する。 |

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
| **Services** | APIクライアントやWebSocket通信など、外部との通信処理をまとめたモジュール。 |

## 3. シーケンス図

### 3.1. ユーザー認証とグラフレイアウト計算

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as Frontend
    participant B as API
    participant DB as Database

    U->>F: ログイン情報入力
    F->>B: /auth/token (ユーザー名, パスワード)
    B->>DB: ユーザー情報検証
    DB-->>B: 検証結果
    B-->>F: JWTトークン
    F->>F: トークンをStoreに保存
    U->>F: レイアウト計算を要求 (GraphMLデータ)
    F->>B: /network/layout (JWT, GraphML)
    B->>B: 認証チェック
    B->>N: /layout (GraphML, アルゴリズム)
    N-->>B: 計算結果 (座標データ)
    B-->>F: 計算結果
    F->>U: グラフを描画
```
