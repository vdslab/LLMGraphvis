# API仕様

本システムは、フロントエンドとバックエンド間の通信、およびバックエンド内部サービス間の通信にRESTful APIとWebSocketを使用する。FastAPIの自動生成されるOpenAPIドキュメント（Swagger UI/ReDoc）が主要なAPIリファレンスとなるが、ここでは主要なAPIエンドポイントとデータモデルの概要を記述する。

## 1. 認証API

### `POST /auth/register`
- **説明**: ユーザー登録
- **リクエストボディ**:
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string"
  }
  ```
- **レスポンス**:
  ```json
  {
    "message": "User registered successfully"
  }
  ```

### `POST /auth/login`
- **説明**: ユーザーログイン
- **リクエストボディ**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **レスポンス**:
  ```json
  {
    "access_token": "string",
    "token_type": "bearer",
    "refresh_token": "string"
  }
  ```

### `POST /auth/refresh`
- **説明**: アクセストークンのリフレッシュ
- **リクエストヘッダー**:
  - `Cookie`: `refresh_token=<refresh_token_string>`
- **レスポンス**:
  ```json
  {
    "access_token": "string",
    "token_type": "bearer"
  }
  ```

### `POST /auth/logout`
- **説明**: ユーザーログアウト
- **リクエストヘッダー**:
  - `Authorization`: `Bearer <access_token_string>`
- **レスポンス**:
  ```json
  {
    "message": "Logged out successfully"
  }
  ```

## 2. グラフデータ管理API

### `POST /projects/{project_id}/upload-graph`
- **説明**: グラフデータ（CSV/JSON）のアップロード
- **パスパラメータ**:
  - `project_id`: プロジェクトID
- **リクエストボディ**:
  - `file`: アップロードするグラフデータファイル
- **レスポンス**:
  ```json
  {
    "message": "Graph data uploaded successfully",
    "graph_id": "string"
  }
  ```

### `GET /projects/{project_id}/graph/{graph_id}`
- **説明**: 特定のグラフデータを取得
- **パスパラメータ**:
  - `project_id`: プロジェクトID
  - `graph_id`: グラフID
- **レスポンス**:
  - グラフデータ（ノード、エッジ情報を含むJSON形式）

## 3. LLMインタラクション (WebSocket)

### `WebSocket /ws/{project_id}/chat`
- **説明**: ユーザーとLLM間のリアルタイムチャットおよびグラフ操作
- **パスパラメータ**:
  - `project_id`: プロジェクトID

#### クライアントからサーバーへのメッセージ
- **ユーザーメッセージ**:
  ```json
  {
    "type": "user_message",
    "content": "友達が多い人を可視化して"
  }
  ```
- **Function Call結果の通知** (LLMからのFunction Call実行後):
  ```json
  {
    "type": "function_result",
    "tool_call_id": "string",
    "result": "any"
  }
  ```

#### サーバーからクライアントへのメッセージ
- **LLMテキスト応答**:
  ```json
  {
    "type": "llm_response",
    "content": "次数中心性をノードサイズに割り当てました。"
  }
  ```
- **Function Call要求** (LLMがFunction Callを提案した場合):
  ```json
  {
    "type": "function_call",
    "tool_call_id": "string",
    "function": {
      "name": "string",
      "arguments": "object"
    }
  }
  ```
- **グラフ描画データ更新**:
  ```json
  {
    "type": "graph_update",
    "patch": "array" // JSON Patch形式の差分データ
  }
  ```
- **エラーメッセージ**:
  ```json
  {
    "type": "error",
    "message": "string"
  }
  ```

## 4. 内部サービス間API

（FastAPIの依存性注入や内部関数呼び出しにより直接連携されるため、明示的なHTTP APIとしては公開されないが、論理的なインターフェースとして存在する）

### 計算サービスインターフェース
- `calculate_metric(project_id: str, graph_id: str, metric_type: str) -> dict`
- `calculate_layout(project_id: str, graph_id: str, layout_type: str) -> dict`

### 状態管理サービスインターフェース
- `update_visualization_state(project_id: str, state_patch: dict) -> None`
- `get_current_visualization_data(project_id: str) -> dict`