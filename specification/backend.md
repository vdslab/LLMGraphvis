# バックエンド仕様 (API)

## 1. 概要

FastAPIで構築されたバックエンドAPI。主な責務は以下の通り。

- ユーザー認証・認可 (OAuth2/JWT)
- ビジネスロジックの実行
- データベースとのやり取り (PostgreSQL)
- `NetworkXMCP`サービスとの連携によるグラフ計算
- `OpenAI API`との連携によるLLM機能の提供
- `Frontend`へのWebSocketによるリアルタイム通知

## 2. APIエンドポイント一覧

### 2.1. 認証 (`/auth`)

| Method | Path | 認証 | 説明 |
|:---|:---|:---:|:---|
| `POST` | `/register` | 不要 | 新規ユーザーを登録する。 |
| `POST` | `/token` | 不要 | ユーザー名とパスワードで認証し、JWTアクセストークンを発行する。 |
| `GET` | `/users/me` | **必要** | 現在認証中のユーザー情報を取得する。 |

### 2.2. チャット・LLM連携 (`/chat`)

| Method | Path | 認証 | 説明 |
|:---|:---|:---:|:---|
| `POST` | `/conversations` | **必要** | 新しい会話を作成する。 |
| `GET` | `/conversations` | **必要** | ユーザーの会話一覧を取得する。 |
| `GET` | `/conversations/{id}` | **必要** | 特定の会話の詳細を取得する。 |
| `GET` | `/conversations/{id}/messages` | **必要** | 特定の会話のメッセージ一覧を取得する。 |
| `POST` | `/conversations/{id}/messages` | **必要** | 会話に新しいメッセージを追加し、LLMによる非同期処理を開始する。 |
| `POST` | `/recommend-layout` | **必要** | ネットワークの概要に基づき、LLMが最適なレイアウトを推薦する。 |
| `POST` | `/process` | **必要** | チャットUIからのメッセージを処理し、LLMやツール呼び出しを含む一連の対話を実行する。 |

### 2.3. ネットワーク (`/network`)

| Method | Path | 認証 | 説明 |
|:---|:---|:---:|:---|
| `GET` | `/{id}/cytoscape` | **必要** | ネットワークデータをCytoscape.js形式のJSONで取得する。 |
| `GET` | `/{id}/export` | **必要** | ネットワークをGraphMLファイルとしてダウンロードする。 |
| `POST` | `/upload` | **必要** | GraphMLファイルをアップロードし、新しい会話とネットワークを作成する。 |
| `POST` | `/{conv_id}/upload` | **必要** | 既存の会話に紐づくネットワークをGraphMLファイルで上書きする。 |
| `POST` | `/{id}/layout` | **必要** | `NetworkXMCP`を呼び出し、指定されたアルゴリズムでグラフレイアウトを計算する。 |

### 2.4. その他

| Method | Path | 認証 | 説明 |
|:---|:---|:---:|:---|
| `GET` | `/` | 不要 | APIのルートエンドポイント。 |
| `GET` | `/health` | 不要 | APIとデータベースのヘルスチェックを行う。 |
| `WS` | `/ws` | **必要** | WebSocket接続を確立する。トークンによる認証が必須。 |

## 3. 主要なデータモデル

APIで利用される主要なデータスキーマ（Pydanticモデル）。

- **`User`**: ユーザー情報を表す。(`id`, `username`)
- **`UserCreate`**: ユーザー登録時に使用。(`username`, `password`)
- **`Token`**: JWTトークンを表す。(`access_token`, `token_type`)
- **`Conversation`**: チャットの会話セッションを表す。(`id`, `title`, `user_id`, `created_at`)
- **`ChatMessage`**: 会話内の各メッセージを表す。(`id`, `content`, `role`, `created_at`)
- **`Network`**: グラフデータを表す。(`id`, `name`, `graphml_content`, `conversation_id`)

## 4. 認証フロー

1.  **ユーザー登録**: `POST /auth/register` に `username` と `password` を送信し、ユーザーを作成する。パスワードはハッシュ化されてDBに保存される。
2.  **トークン発行**: `POST /auth/token` に `username` と `password` をフォームデータとして送信する。
3.  **認証成功**: APIはユーザーを検証し、有効期限付きのJWTアクセストークンを返す。
4.  **APIアクセス**: `Frontend`は以降のリクエストの `Authorization` ヘッダーに `Bearer {token}` を含めて送信する。
5.  **サーバー検証**: APIは各リクエストでトークンを検証し、有効であればリクエストを処理する。

## 5. 外部サービス連携

### 5.1. NetworkXMCPサービス

- **役割**: CPU負荷の高いグラフ計算（レイアウト計算、指標分析、フォーマット変換など）を専門に扱うマイクロサービス。
- **連携方法**: APIサービスはHTTPリクエストで`NetworkXMCP`の各エンドポイントを呼び出す。
    - 例: レイアウト計算時、APIは `POST /network/{id}/layout` を受け取ると、現在のGraphMLデータとレイアウト種別を `NetworkXMCP` の `/tools/change_layout` に送信し、計算結果（座標が更新されたGraphML）を受け取る。
- **エンドポイント**: `http://networkx-mcp:8001` (Docker内部)

### 5.2. OpenAI API

- **役割**: 自然言語処理機能を提供し、ユーザーとの対話的な分析を可能にする。
- **連携方法**: `services/llm.py` 内の `process_chat_message` 関数がOpenAIのChat Completions APIを呼び出す。
- **主な用途**:
    1.  **レイアウト推薦**: `POST /chat/recommend-layout` で、ユーザーが記述したネットワークの特徴と目的に基づき、最適なレイアウトアルゴリズムとパラメータを推薦する。
    2.  **ツール呼び出し**: チャットでのユーザーの指示を解釈し、「中心性を計算して」「コミュニティを検出して」といった指示を`NetworkXMCP`を呼び出すためのJSON形式のツールコールに変換する。
    3.  **結果の要約**: `NetworkXMCP`から返された計算結果（数値データなど）を解釈し、自然言語でユーザーに分かりやすく説明する。

## 6. WebSocket通信

- **エンドポイント**: `/ws?token={jwt_token}`
- **目的**: `Frontend`に対して、サーバーサイドで発生したイベント（例: LLMによる分析完了、ネットワーク更新）をリアルタイムに通知する。
- **接続フロー**:
    1. `Frontend`は認証後に取得したJWTトークンをクエリパラメータに付与してWebSocket接続を要求する。
    2. サーバーはトークンを検証し、有効であれば接続を確立する。
    3. `ConnectionManager`がクライアントごとの接続を管理する。
- **通知**: バックグラウンドタスク（LLM処理など）が完了すると、`app.state.ws_manager.broadcast()` を通じて接続中の全クライアント（または特定のクライアント）に更新情報を送信する。
