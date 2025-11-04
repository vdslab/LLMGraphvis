# 1. アーキテクチャ設計

## 1.1. C4モデル

本ドキュメントでは、システムの構造を段階的に理解しやすくするために「C4モデル」という考え方を採用し、概観（コンテキスト）から詳細（コンテナ）へと掘り下げて説明します。

### 1.1.1. コンテキスト図 (Context Diagram)

システム全体の概観を示します。ユーザーがどのようにシステムとやり取りし、どの外部システムと連携するかを表します。

```mermaid
graph TD
    subgraph "LLMGraph-vis"
        webApplication["Web Application"]
    end

    user["ユーザー"] -- "自然言語によるグラフ操作コマンド" --> webApplication
    webApplication -- "グラフ構造の可視化表示" --> user
    webApplication -- "レイアウト推薦・チャット" --> llmServices["LLM Services"]

    style user fill:#d1e0ff,stroke:#333,stroke-width:2px
    style llmServices fill:#ffccd1,stroke:#333,stroke-width:2px
```

| 要素 | 説明 |
|:---|:---|
| **ユーザー** | グラフの可視化や分析を行う研究者や開発者。 |
| **Web Application** | 本システムのコア機能を提供するWebアプリケーション。 |
| **LLM Services** | グラフのレイアウト推薦やチャット機能のために利用する外部の大規模言語モデルサービス。(OpenAI API, Google Geminiなど) | 外部LLM API (例: OpenAI, Google Gemini) |

### 1.1.2. コンテナ図 (Container Diagram)

アプリケーションを構成する主要なコンテナ（サービス）と、それらの間のデータの流れを示します。

```mermaid
graph TD
    user[ユーザー] -- "HTTPS" --> webBrowser["Web Browser"]

    subgraph "Docker Environment"
        frontendService["Frontend Service"]
        apiService["API Service"]
        networkXMCP["NetworkX MCP"]
        database[("Database")]
    end

    webBrowser -- "Loads SPA (HTTPS)" --> frontendService
    webBrowser -- "API (HTTPS)" --> apiService

    apiService -- "グラフ計算を依頼 (API/HTTP)" --> networkXMCP
    apiService -- "ユーザーデータ、会話履歴などを保存 (PostgreSQL)" --> database
    networkXMCP -- "計算結果の属性を保存 (PostgreSQL)" --> database
    apiService -- "API (HTTPS)" --> llmService[LLM Services]

    style webBrowser fill:#d1e0ff,stroke:#333,stroke-width:2px
    style frontendService fill:#82b3ff,stroke:#333,stroke-width:2px
    style apiService fill:#94e2d5,stroke:#333,stroke-width:2px
    style networkXMCP fill:#f5c2e7,stroke:#333,stroke-width:2px
    style database fill:#f9e2af,stroke:#333,stroke-width:2px
```

| コンテナ | 説明 | 技術スタック |
|:---|:---|:---|
| **Frontend Service** | ユーザーにUIを提供するためのSPA（Single Page Application）を配信するWebサーバー。詳細は[フロントエンド仕様](./Frontend.md)を参照。 | React, Vite, react-force-graph-2d, Zustand, axios |
| **API Service** | ビジネスロジック、認証、外部API連携を担当するバックエンド。詳細は[バックエンド仕様](./Backend.md)を参照。 | FastAPI, SQLAlchemy, (LLM SDKs) |
| **NetworkX Model Context Protocol (NetworkXMCP)** | グラフ計算やレイアウト処理に特化した計算サービス。**ステートフル**であることで、計算結果をキャッシュし、高コストな再計算を回避します。詳細は[グラフ計算サービス仕様](./NetworkXMCP.md)を参照。 | FastAPI, NetworkX, Python, SQLAlchemy |
| **Database** | ユーザー情報、グラフデータ、計算結果のキャッシュなどを永続化するデータベース。詳細は[データベーススキーマ仕様](./database-schema.md)を参照。 | PostgreSQL |

## 1.2. データ永続化

本システムにおけるデータの永続化は、目的の異なる2つの仕組みによって実現されています。

- **サーバーサイド (Database)**:
    - **目的**: アプリケーションのコアとなるデータを安全に保管し、ユーザーセッションを跨いで状態を維持する。
    - **技術**: PostgreSQL
    - **永続化されるデータ**:
        - ユーザーアカウント情報（ハッシュ化されたパスワードを含む）
        - 各ユーザーの会話履歴
        - メッセージ（ユーザーの発言、LLMの応答）
        - GraphMLデータ本体
        - グラフの永続的な属性データ（元データ由来、または計算によって追加されたレイアウト座標や中心性指標など）
    - **補足**: 主要なテーブルの構造については、[データベーススキーマ仕様](./database-schema.md)で詳細を定義しています。

- **クライアントサイド (Web Browser)**:
    - **目的**: ユーザーの利便性向上。再ログインの手間を省き、シームレスな認証状態を維持する。
    - **技術**: `HttpOnly`属性を付与したCookie
    - **永続化されるデータ**:
        - 認証用のJSON Web Token (JWT)
    - **役割**: API Serviceが発行したJWTをブラウザがCookieとして安全に保存する。以降のAPIリクエストでは、ブラウザが自動的にCookieをリクエストヘッダーに含めて送信するため、クライアントサイドのJavaScriptがトークンにアクセスする必要はない。
    - **セキュリティ**: `HttpOnly`属性により、JavaScriptからのCookieへのアクセスが禁止されるため、XSS（クロスサイトスクリプティング）攻撃によるトークン窃取のリスクを大幅に軽減します。これは、`localStorage`を利用する方法よりも安全です。

## 1.3. リアルタイム通信方針

本システムでは、サーバーからクライアントへの非同期な情報通知のために、**Server-Sent Events (SSE)** を採用します。

- **採用理由**: 長時間かかる処理の完了通知や進捗状況のストリーミングにおいて、クライアントが定期的に問い合わせる（ポーリングする）方式よりも効率的です。また、双方向通信が不要な本システムの主なユースケースにおいては、WebSocketよりも実装が容易で、既存のHTTPインフラをそのまま活用できるメリットが大きいためです。

- **主な用途**:
    - グラフ操作（計算・可視化適用）の完了通知
    - 大規模グラフにおけるレイアウト計算などの進捗通知
    - LLMの思考プロセスやツール実行状況のストリーミング

- **将来的な展望**: 共同編集機能など、クライアントからのリアルタイムな通信（双方向通信）が必須となる機能を実装する場合は、その機能のために別途WebSocketの導入を検討します。