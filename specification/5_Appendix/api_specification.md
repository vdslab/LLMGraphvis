# LLMGraphvis API仕様書

## 概要

LLMGraphvis APIは、グラフデータの管理、可視化、分析を行うためのRESTful APIです。このAPIを使用することで、GraphMLファイルのアップロード、ネットワークの可視化、レイアウトの計算、中心性指標の計算などを行うことができます。

## ベースURL

```
https://api.llmgraphvis.example.com/
```

## 認証

APIの多くのエンドポイントでは認証が必要です。認証には、JWTトークンを使用します。

### 認証ヘッダー

```
Authorization: Bearer {token}
```

### 認証エンドポイント

#### ユーザー登録

```
POST /auth/register
```

**リクエスト**:

```json
{
  "username": "user123",
  "password": "securepassword"
}
```

**レスポンス**:

```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "user123",
    "is_active": true,
    "created_at": "2025-11-13T05:27:00.000Z",
    "updated_at": null
  }
}
```

#### ログイン

```
POST /auth/token
```

**リクエスト**:

```json
{
  "username": "user123",
  "password": "securepassword"
}
```

**レスポンス**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

## エンドポイント

### ネットワーク管理

#### ネットワークのアップロード

```
POST /network/upload
```

**リクエスト**:
- Content-Type: multipart/form-data
- ファイル: GraphMLファイル

**レスポンス**:

```json
{
  "conversation_id": 1,
  "network_id": 1
}
```

#### 既存ネットワークの上書き

```
POST /network/{conversation_id}/upload
```

**リクエスト**:
- Content-Type: multipart/form-data
- ファイル: GraphMLファイル

**レスポンス**:

```json
{
  "id": 1,
  "name": "network.graphml",
  "conversation_id": 1,
  "created_at": "2025-11-13T05:27:00.000Z",
  "updated_at": "2025-11-13T05:28:00.000Z"
}
```

#### ネットワークのエクスポート

```
GET /network/{network_id}/export
```

**レスポンス**:
- Content-Type: application/xml
- Content-Disposition: attachment; filename=network_{network_id}.graphml
- GraphMLファイルの内容

### ネットワーク可視化

#### Cytoscape.js形式のデータ取得

```
GET /network/{network_id}/cytoscape
```

**レスポンス**:

```json
{
  "elements": {
    "nodes": [
      {
        "data": {
          "id": "1",
          "name": "Node 1",
          "size": 5.0,
          "color": "#1d4ed8"
        },
        "position": {
          "x": 0.5,
          "y": 0.3
        }
      },
      ...
    ],
    "edges": [
      {
        "data": {
          "source": "1",
          "target": "2",
          "width": 1.0,
          "color": "#94a3b8"
        }
      },
      ...
    ]
  }
}
```

#### 可視化データの取得

```
GET /network/{network_id}/visdata
```

**レスポンス**:

```json
{
  "nodes": [
    {
      "id": "1",
      "label": "Node 1",
      "x": 0.5,
      "y": 0.3,
      "size": 5.0,
      "color": "#1d4ed8"
    },
    ...
  ],
  "links": [
    {
      "source": "1",
      "target": "2",
      "width": 1.0,
      "color": "#94a3b8"
    },
    ...
  ]
}
```

### レイアウト計算

```
POST /network/{network_id}/layout
```

**リクエスト**:

```json
{
  "layout_type": "spring",
  "layout_params": {
    "k": 0.3,
    "iterations": 100
  }
}
```

**レスポンス**:

```json
{
  "result": {
    "success": true,
    "layout_type": "spring",
    "positions": {
      "1": {
        "x": 0.5,
        "y": 0.3
      },
      "2": {
        "x": 0.7,
        "y": 0.2
      },
      ...
    }
  }
}
```

### 中心性計算

```
POST /network/{network_id}/centrality
```

**リクエスト**:

```json
{
  "centrality_type": "degree",
  "centrality_params": {}
}
```

**レスポンス**:

```json
{
  "result": {
    "success": true,
    "centrality_type": "degree",
    "centrality_values": {
      "1": 0.8,
      "2": 0.5,
      ...
    }
  }
}
```

### 会話管理

#### 会話の作成

```
POST /conversation
```

**リクエスト**:

```json
{
  "title": "New Conversation"
}
```

**レスポンス**:

```json
{
  "id": 1,
  "title": "New Conversation",
  "user_id": 1,
  "created_at": "2025-11-13T05:27:00.000Z",
  "updated_at": null
}
```

#### 会話の取得

```
GET /conversation/{conversation_id}
```

**レスポンス**:

```json
{
  "id": 1,
  "title": "New Conversation",
  "user_id": 1,
  "created_at": "2025-11-13T05:27:00.000Z",
  "updated_at": null,
  "network": {
    "id": 1,
    "name": "network.graphml",
    "conversation_id": 1,
    "created_at": "2025-11-13T05:27:00.000Z",
    "updated_at": null
  }
}
```

#### 会話の一覧取得

```
GET /conversation
```

**レスポンス**:

```json
[
  {
    "id": 1,
    "title": "New Conversation",
    "user_id": 1,
    "created_at": "2025-11-13T05:27:00.000Z",
    "updated_at": null
  },
  ...
]
```

### チャットメッセージ

#### メッセージの送信

```
POST /chat/{conversation_id}/message
```

**リクエスト**:

```json
{
  "content": "Tell me about this network",
  "role": "user"
}
```

**レスポンス**:

```json
{
  "id": 1,
  "content": "Tell me about this network",
  "role": "user",
  "user_id": 1,
  "conversation_id": 1,
  "created_at": "2025-11-13T05:27:00.000Z"
}
```

#### メッセージの取得

```
GET /chat/{conversation_id}/message
```

**レスポンス**:

```json
[
  {
    "id": 1,
    "content": "Tell me about this network",
    "role": "user",
    "user_id": 1,
    "conversation_id": 1,
    "created_at": "2025-11-13T05:27:00.000Z"
  },
  {
    "id": 2,
    "content": "This network has 10 nodes and 15 edges...",
    "role": "assistant",
    "user_id": 1,
    "conversation_id": 1,
    "created_at": "2025-11-13T05:27:10.000Z"
  },
  ...
]
```

## エラーレスポンス

エラーが発生した場合、APIは以下の形式でエラーレスポンスを返します。

```json
{
  "success": false,
  "error_code": "ERROR_CODE",
  "message": "Error message",
  "context": {
    "key1": "value1",
    "key2": "value2"
  },
  "timestamp": "2025-11-13T05:27:00.000Z"
}
```

### 主なエラーコード

| エラーコード | 説明 | HTTPステータスコード |
|------------|------|-------------------|
| `VALIDATION_ERROR` | リクエストの検証に失敗した | 400 |
| `AUTHENTICATION_ERROR` | 認証に失敗した | 401 |
| `PERMISSION_DENIED_ERROR` | 権限がない | 403 |
| `RESOURCE_NOT_FOUND_ERROR` | リソースが見つからない | 404 |
| `GRAPHML_VALIDATION_ERROR` | GraphMLの検証に失敗した | 400 |
| `GRAPH_PROCESSING_ERROR` | グラフ処理に失敗した | 500 |
| `MCP_COMMUNICATION_ERROR` | MCPサービスとの通信に失敗した | 502 |
| `DATABASE_COMMUNICATION_ERROR` | データベースとの通信に失敗した | 503 |
| `INTERNAL_SERVER_ERROR` | サーバー内部エラー | 500 |

## データモデル

### User

```json
{
  "id": 1,
  "username": "user123",
  "is_active": true,
  "created_at": "2025-11-13T05:27:00.000Z",
  "updated_at": null
}
```

### Conversation

```json
{
  "id": 1,
  "title": "New Conversation",
  "user_id": 1,
  "created_at": "2025-11-13T05:27:00.000Z",
  "updated_at": null,
  "network": {
    "id": 1,
    "name": "network.graphml",
    "conversation_id": 1,
    "created_at": "2025-11-13T05:27:00.000Z",
    "updated_at": null
  }
}
```

### Network

```json
{
  "id": 1,
  "name": "network.graphml",
  "conversation_id": 1,
  "created_at": "2025-11-13T05:27:00.000Z",
  "updated_at": null
}
```

### ChatMessage

```json
{
  "id": 1,
  "content": "Tell me about this network",
  "role": "user",
  "user_id": 1,
  "conversation_id": 1,
  "created_at": "2025-11-13T05:27:00.000Z"
}
```

## ページネーション

一部のエンドポイントでは、ページネーションをサポートしています。ページネーションを使用するには、以下のクエリパラメータを指定します。

- `page`: ページ番号（デフォルト: 1）
- `page_size`: ページサイズ（デフォルト: 10、最大: 100）

ページネーションを使用するエンドポイントのレスポンスは、以下の形式になります。

```json
{
  "success": true,
  "items": [
    ...
  ],
  "total": 100,
  "page": 1,
  "page_size": 10,
  "total_pages": 10
}
```

## レート制限

APIにはレート制限があります。レート制限を超えると、以下のエラーレスポンスが返されます。

```json
{
  "success": false,
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded",
  "context": {
    "limit": 100,
    "reset": "2025-11-13T05:28:00.000Z"
  },
  "timestamp": "2025-11-13T05:27:00.000Z"
}
```

## バージョニング

APIのバージョンは、リクエストヘッダーで指定できます。

```
Accept: application/json; version=1.0
```

現在サポートされているバージョンは以下の通りです。

- 1.0: 現在のバージョン