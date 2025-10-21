# LLM駆動型インタラクティブグラフ分析ツール 設計書

## 1. システム概要

本システムは、ユーザーがアップロードしたネットワーク(グラフ)データを、LLM(大規模言語モデル)との対話形式で可視化・分析するためのWebアプリケーションである。ユーザーは「友達が多い人を大きく表示して」といった曖昧な自然言語や、「次数中心性をノードサイズに割り当てて」といった厳密な指示により、グラフのレイアウト、ノードのサイズや色などをインタラクティブに変更できる。これにより、ネットワーク可視化の専門知識の有無にかかわらず、直感的で容易なデータ探索体験を提供することを目的とする。

## 2. アーキテクチャ設計

### 2.1. 設計原則

- **厳格な役割分離**: フロントエンドは描画とユーザー入出力のみを担当し、一切の計算処理やビジネスロジックを持たない。
- **バックエンド集中処理**: すべてのビジネスロジック、データ処理、LLM連携、認証はバックエンドで完結させる。
- **ステートフルな可視化**: バックエンドは、ユーザーセッションごとに現在の可視化設定(例：ノードサイズ＝次数中心性)を状態(ステート)として管理する。
- **非同期・ノンブロッキング**: 計算負荷の高い処理は非同期タスクキューで実行し、システムの応答性を確保する。
- **計算結果の永続化**: 一度計算したネットワーク指標やレイアウト座標はデータベースに永続化し、再計算のコストを削減する。
- **セキュリティ・バイ・デザイン**: 認証・認可、およびLLMとの連携において、セキュリティを最優先に考慮した設計を行う。

### 2.2. 高レベルアーキテクチャ

本システムは、単一の技術選定が他の技術選定に影響を与える、相互に関連した要件を持つ。インタラクティブな体験にはリアルタイム更新(**WebSocket**)が不可欠であり、これは非同期フレームワーク(**FastAPI**)で効率的に扱われる。複雑なグラフ分析はバックグラウンドタスク(**Celery**)を必要とし、これも非同期で管理される。このため、システム全体として非同期処理を前提としたコンポーネント群で構成される。

```mermaid
graph TD
    subgraph "User"
        UserClient[Browser]
    end

    subgraph "Frontend"
        WebApp[React App w/ Sigma.js]
    end

    subgraph "Backend (FastAPI)"
        APIGateway[API Gateway]
        Orchestrator[Orchestrator / LLM Service]
        ComputeEngine["Compute Engine<br>(Celery Workers)"]
        StateManager[State Manager]
        AuthService[Auth Service]
    END

    subgraph "Data Stores"
        PostgresDB["PostgreSQL<br>- Users, Projects, History"]
        Neo4jDB["Neo4j<br>- Graph Topology"]
        RedisDB["Redis<br>- Cache, Pub/Sub, Sessions"]
    end

    subgraph "Infrastructure & External Services"
        LLM_API[LLM API (Gemini)]
        RabbitMQ_Broker["RabbitMQ<br>Message Broker"]
    end

    %% Connections
    UserClient -- "User Interaction" --> WebApp
    WebApp -- "HTTP / WebSocket API" --> APIGateway

    APIGateway -- "Authenticate" --> AuthService
    APIGateway -- "Route Requests" --> Orchestrator
    APIGateway -- "Manage Connections" --> StateManager

    Orchestrator -- "Send Prompts" --> LLM_API
    Orchestrator -- "Dispatch Tasks" --> RabbitMQ_Broker
    Orchestrator -- "Update State" --> StateManager
    Orchestrator -- "Access Project Data" --> PostgresDB

    RabbitMQ_Broker -- "Deliver Tasks" --> ComputeEngine

    ComputeEngine -- "Read Graph" --> Neo4jDB
    ComputeEngine -- "Write Results" --> RedisDB

    StateManager -- "Push State (WebSocket)" --> WebApp
    StateManager -- "Read Graph/Data" --> Neo4jDB
    StateManager -- "Read Cache/State" --> RedisDB
    StateManager -- "Use for Scaling (Pub/Sub)" --> RedisDB

    AuthService -- "Access User Data" --> PostgresDB
```

---

## 3. コンポーネント詳細

### 3.1. フロントエンド (Client)

- **責務**:
  - ユーザーインターフェース (UI) の提供(チャット画面、可視化描画エリア)。
  - ユーザー認証(ログイン/ログアウト)のインターフェース。
  - グラフデータ(CSV, JSONなど)のアップロード。
  - チャットメッセージの入力とバックエンドへの送信 (WebSocket)。
  - バックエンドから受信した描画データ(JSON)に基づくグラフの描画・更新。
- **技術選定**:
  - **可視化ライブラリ**: **Sigma.js** を推奨する。WebGLベースであり、数万ノード規模の大規模グラフにおいても高いインタラクティブ性能を維持できるため。D3.jsは柔軟性が高いが、大規模描画には不向きなため、補助的なチャートでの利用に限定する。
- **状態同期とUI**:
  - **リアルタイム同期**: バックエンドとの状態同期には **WebSocket** を用いる。バックエンドが状態の「信頼できる唯一の情報源(Source of Truth)」となる。
  - **効率的なデータ転送**: 状態更新時には、状態オブジェクト全体ではなく **JSON Patch (RFC 6902)** 形式で差分のみを送信し、ネットワーク帯域を効率化する。
  - **ユーザーエクスペリエンス**: **オプティミスティックUI** を採用。ユーザー操作を即座にUIに反映させ、バックエンドからの確定情報を待つことで、体感的な応答性を向上させる。

### 3.2. バックエンド (Backend)

- **フレームワーク**: **FastAPI**
  - **選定理由**: ネイティブな非同期サポートにより、HTTPリクエスト、WebSocket接続、非同期タスクキュー(Celery)といった複数のI/Oバウンド処理を単一イベントループ内で効率的に並行処理できる。API中心のアーキテクチャに最適であり、自動APIドキュメント生成やPydanticによる厳格な型検証機能が開発効率と堅牢性を高める。

#### A. APIゲートウェイ (API Gateway)

- **責務**:
  - フロントエンドからのすべてのリクエスト(HTTPおよびWebSocket)の単一窓口。
  - リクエストの認証(**認証サービス**と連携)。
  - リクエスト内容に基づき、適切な内部サービスに処理をルーティングする。

#### B. 認証サービス (Auth Service)

- **責務**:
  - ユーザー登録、ログイン、ログアウト処理。
  - **JWT (JSON Web Token)** を用いたセッショントークンの発行と検証。
- **認証フロー**:
  - **アクセストークン**: 短命(例: 15分)のJWT。APIリクエスト時に`Authorization`ヘッダーで送信。
  - **リフレッシュトークン**: 長命(例: 7日)のトークン。**安全な`HttpOnly`クッキー**に保存し、XSSによるトークン盗難リスクを緩和する。
- **トークン失効**:
  - JWTはステートレスなため、本質的に失効が困難である。この対策として、失効したリフレッシュトークンのIDを**Redis**のブラックリストで管理する。

#### C. チャット / LLMサービス (Orchestrator)

- **責務**:
  - システムの中核。ユーザーの自然言語指示を解釈し、必要な処理をオーケストレーションする。
  - **LLM Function Calling** を活用し、ユーザーの意図を具体的な関数呼び出しに変換する。
- **LLM連携フロー**:
  1.  ユーザーのクエリと定義済み関数スキーマをLLMに送信。
  2.  LLMが返すJSON(呼び出すべき関数と引数)を解析・検証。
  3.  対応する内部サービス(計算サービス、状態管理サービス)を呼び出す。
- **プロンプトエンジニアリング**:
  - 「重要なノード」のような曖昧な指示に対し、LLMが明確化のための質問(例: 「重要性を判断する指標はどれですか？」)を返すようにプロンプトを設計する(**Ask-when-Needed**)。
  - 複雑なタスクには、思考の連鎖(**Chain-of-Thought**)を促し、複数の関数呼び出しを計画・実行させる。
- **セキュリティ**:
  - LLMが生成した関数呼び出しは**信頼できない入力**として扱う。実行前に、関数名のホワイトリスト検証、引数の型・値の厳格な検証(Pydanticモデル使用)、入力のサニタイズを徹底する。

#### D. 計算サービス (Compute Engine)

- **責務**:
  - ネットワーク分析(各種中心性、コミュニティ検出)やレイアウト計算など、計算負荷の高い処理を実行する。
- **非同期タスク処理**:
  - **Celery** とメッセージブローカー **RabbitMQ** を使用。
  - Orchestratorからのリクエストを受け、計算タスクを即座にキューに投入。APIサーバーのブロッキングを防ぐ。
  - 計算完了後、結果を**計算結果DB (Redis)**に保存し、必要に応じてWebSocket経由で完了通知を送信する。

#### E. 可視化状態管理サービス (State Manager)

- **責務**:
  - プロジェクトごとに現在の「可視化設定(マッピング状態)」を管理する。
  - Orchestratorからの要求に基づき状態を更新し、フロントエンド向けの最終的な**描画用JSON**を生成してプッシュする。
- **リアルタイム同期アーキテクチャ**:
  - 水平スケーリングに対応するため、WebSocket接続状態の管理には **Redis Pub/Sub** を利用する。
  - 状態変更時、特定のチャンネルに更新情報をPublish。全サーバーインスタンスがこれをSubscribeし、担当するクライアントに情報を届けることで、サーバー間での状態同期を実現する。

### 3.3. データストア (Data Persistence)

本システムは、データの特性に応じて複数のデータベースを使い分ける**ポリグロット永続化戦略**を採用する。

| テクノロジー   | プライマリデータモデル | アーキテクチャにおける役割                 | 保存されるデータ                                                                     | 主な強み                                                                                         |
| :------------- | :--------------------- | :----------------------------------------- | :----------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------- |
| **Neo4j**      | プロパティグラフ       | グラフのトポロジーの永続的ストレージ       | ノード、エッジ、およびそれらの内在的プロパティ                                       | グラフ構造のネイティブな保存と、Cypherによる効率的なトラバーサルおよびパターンマッチングクエリ。 |
| **Redis**      | キーバリュー           | 高速キャッシュ層およびメッセージブローカー | 計算済みメトリクス、レイアウト座標、WebSocket接続状態、タスクキュー、JWT失効リスト。 | サブミリ秒のレイテンシでのデータ読み書き。Pub/Sub機能によるスケーラブルな状態同期。              |
| **PostgreSQL** | リレーショナル         | アプリケーションのプライマリデータベース   | ユーザーアカウント、プロジェクトメタデータ、認証情報、保存された設定、チャット履歴。 | ACID準拠による強力なデータ整合性とトランザクションの信頼性。成熟したエコシステム。               |

---

## 4. データフローの具体例

**シナリオ: ユーザーが「友達が多い人を可視化して」と入力**

1.  **FE**: ユーザー入力をWebSocketで **API Gateway** に送信。
2.  **API Gateway**: 認証後、 **Orchestrator** にメッセージを転送。
3.  **Orchestrator**:
    - LLMに「"友達が多い人を可視化して"」と問い合わせる。
    - LLMが応答 → `Function Call: calculate_metric(metric='degree_centrality')`
4.  **Orchestrator** が **Compute Engine** に「次数中心性」の計算を依頼(Celeryタスクをディスパッチ)。
5.  **Compute Engine**:
    - **Redis**をチェック(結果はまだ無い)。
    - **Neo4j**からグラフデータを取得し、次数中心性を計算。
    - 結果を**Redis**に保存。
    - 計算結果を **Orchestrator** に返す。
6.  **Orchestrator**:
    - LLMに「計算結果は ... です。元の指示は『可視化して』です。」と再度問い合わせる。
    - LLMが分析 → 「友達が多い(次数中心性が高い)」を「可視化(サイズ割り当て)」と判断。
    - LLMが応答 → `Function Call: map_visual_property(property='node_size', metric='degree_centrality')`
7.  **Orchestrator** が **State Manager** に「ノードサイズを次数中心性にマッピング」するよう依頼。
8.  **State Manager**:
    - 内部の可視化状態を `{ node_size: 'degree_centrality' }` に更新。
    - **Neo4j** (ノードリスト) と **Redis** (次数中心性の値, 既存のレイアウト座標) からデータを取得・マージ。
    - 最終的な描画JSON(差分)を生成し、WebSocketで **FE** にプッシュする。
9.  **FE**: 新しい描画JSONを受信し、画面のグラフを更新(ノードサイズが変わる)。
10. **Orchestrator**: (並行して)LLMからのテキスト応答「次数中心性をノードサイズに割り当てました。」をFEに送信。
11. **FE**: チャット欄に応答テキストを表示する。

---

## 5. 実装ロードマップ

1.  **フェーズ1: コアバックエンドとデータ層**
    - FastAPI、ユーザーモデル用のPostgreSQL、およびNeo4jをセットアップ。データ投入パイプラインを実装。
2.  **フェーズ2: 基本的な可視化**
    - Sigma.jsを用いてフロントエンドを開発。Neo4jからグラフをロードし、単純なRESTコールでフロントエンドに送信するAPIを実装。
3.  **フェーズ3: 非同期分析**
    - Celery/RabbitMQとRedisを統合。グラフ計算ロジックをバックグラウンドタスクに移行し、結果のRedisキャッシュを実装。
4.  **フェーズ4: リアルタイム同期**
    - RESTベースのデータ更新をWebSocket接続に置き換え。Redis Pub/SubとJSON Patchを使用した状態同期ロジックを実装。
5.  **フェーズ5: LLM統合**
    - Function Callingスキーマとプロンプトエンジニアリングロジックを開発。LLMが生成したコマンドの検証層を実装。
6.  **フェーズ6: セキュリティと本番環境対応**
    - HttpOnlyクッキーとRedisベースの失効リストを含む完全なJWTアクセス/リフレッシュトークンフローを実装。本番環境へのデプロイメントを設定。
