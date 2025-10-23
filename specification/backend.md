# バックエンド仕様 (Application Programming Interface)

## 1. 概要

FastAPIで構築されたバックエンドAPI。主な責務は以下の通り。

- ユーザー認証・認可 (OAuth2/JSON Web Token)
- ビジネスロジックの実行
- データベースとのやり取り (PostgreSQL)
- `NetworkX Model Context Protocol` サービスとの連携によるグラフ計算
- 大規模言語モデル (LLM) サービスとの連携による機能提供 (OpenAI API, Google Gemini)

## 2. データ永続化

- **データベース (PostgreSQL)**: ユーザー情報、会話履歴、メッセージ、グラフデータなど、アプリケーションの主要なデータを永続化します。
- **役割**: データの整合性を保ち、複数セッションを跨いでユーザーの状態を維持します。

## 3. APIエンドポイント一覧

### 3.1. 認証 (`/auth`)

| Method | Path | 認証 | 説明 |
|:---|:---|:---:|:---|
| `POST` | `/register` | 不要 | 新規ユーザーを登録する。 |
| `POST` | `/token` | 不要 | ユーザー名とパスワードで認証し、JSON Web Token (JWT) アクセストークンを発行する。 |
| `GET` | `/users/me` | **必要** | 現在認証中のユーザー情報を取得する。 |

### 3.2. チャット・LLM連携 (`/chat`)

| Method | Path | 認証 | 説明 |
|:---|:---|:---:|:---|
| `POST` | `/conversations` | **必要** | 新しい会話を作成する。 |
| `GET` | `/conversations` | **必要** | ユーザーの会話一覧を取得する。 |
| `GET` | `/conversations/{id}` | **必要** | 特定の会話の詳細を取得する。 |
| `GET` | `/conversations/{id}/messages` | **必要** | 特定の会話のメッセージ一覧を取得する。 |
| `POST` | `/conversations/{id}/messages` | **必要** | 会話に新しいメッセージを追加し、LLMによる非同期のバックグラウンド処理を開始する。 |
| `POST` | `/recommend-layout` | **必要** | ネットワークの概要に基づき、LLMが最適なレイアウトを推薦する。 |
| `POST` | `/process` | **必要** | チャットUIからのメッセージを同期的に処理し、LLMやツール呼び出しを含む一連の対話を実行して最終結果を返す。 |

### 3.3. ネットワーク (`/network`)

| Method | Path | 認証 | 説明 |
|:---|:---|:---:|:---|
| `GET` | `/{network_id}/cytoscape` | **必要** | ネットワークデータをCytoscape.js形式のJSONで取得する。 |
| `GET` | `/{network_id}/export` | **必要** | ネットワークをGraphMLファイルとしてダウンロードする。 |
| `POST` | `/upload` | **必要** | GraphMLファイルをアップロードし、新しい会話とネットワークを作成する。 |
| `POST` | `/{conversation_id}/upload` | **必要** | 既存の会話に紐づくネットワークをGraphMLファイルで上書きする。 |
| `POST` | `/{network_id}/layout` | **必要** | `NetworkXMCP`を呼び出してレイアウトを計算し、結果の座標でGraphMLを更新してデータベースに保存する。 |

## 4. 主要なデータモデル

APIで利用される主要なデータスキーマ（Pydanticモデル）。

- **`User`**: ユーザー情報を表す。(`id`, `username`)
- **`UserCreate`**: ユーザー登録時に使用。(`username`, `password`)
- **`Token`**: JSON Web Tokenを表す。(`access_token`, `token_type`)
- **`Conversation`**: チャットの会話セッションを表す。(`id`, `title`, `user_id`, `created_at`)
- **`ChatMessage`**: 会話内の各メッセージを表す。(`id`, `content`, `role`, `created_at`)
- **`Network`**: グラフデータを表す。(`id`, `name`, `graphml_content`, `conversation_id`, `layout_cache`, `centrality_cache`)

## 5. 認証フロー

1.  **ユーザー登録**: `POST /auth/register` に `username` と `password` を送信し、ユーザーを作成する。パスワードはハッシュ化されてデータベースに保存される。
2.  **トークン発行**: `POST /auth/token` に `username` と `password` をフォームデータとして送信する。
3.  **認証成功**: APIはユーザーを検証し、有効期限付きのJWTアクセストークンを返す。
4.  **APIアクセス**: `Frontend`は以降のリクエストの `Authorization` ヘッダーに `Bearer {token}` を含めて送信する。
5.  **サーバー検証**: APIは各リクエストでトークンを検証し、有効であればリクエストを処理する。

## 6. 外部サービス連携

### 6.1. NetworkX Model Context Protocol (NetworkXMCP) サービス

- **役割**: グラフ計算と結果のキャッシュを管理するステートフルなマイクロサービス。
- **連携方法**: APIサービスは、計算が必要なリクエストを単純に`NetworkXMCP`の各エンドポイントに転送（プロキシ）する。
    - 例: レイアウト計算時、APIは `POST /network/{network_id}/layout` を受け取ると、リクエスト内容をそのまま`NetworkXMCP`の `/tools/change_layout` に送信する。実際の計算やキャッシュ管理は`NetworkXMCP`側で行われる。
- **エンドポイント**: `http://networkx-mcp:8001` (Docker内部)

### 6.2. 大規模言語モデル (LLM) サービス

- **役割**: 自然言語処理機能を提供し、ユーザーとの対話的な分析を可能にする。(OpenAI API, Google Geminiに対応)
- **連携方法**: `services/llm.py` 内の `process_chat_message` 関数がLLMのAPIを呼び出す。
- **主な用途**:
    1.  **レイアウト推薦**: `POST /chat/recommend-layout` で、ユーザーが記述したネットワークの特徴と目的に基づき、最適なレイアウトアルゴリズムとパラメータを推薦する。
    2.  **ツール呼び出し**: チャットでのユーザーの指示を解釈し、「中心性を計算して」「コミュニティを検出して」といった指示を`NetworkXMCP`を呼び出すためのJSON形式のツールコールに変換する。
    3.  **結果の要約**: `NetworkXMCP`から返された計算結果（数値データなど）を解釈し、自然言語でユーザーに分かりやすく説明する。