# 4. データベーススキーマ仕様

**前提知識レベル:**
- リレーショナルデータベースおよびSQLに関する基本的な知識
- ER図の読解能力

このドキュメントでは、GraphVisAgentアプリケーションで使用される主要なデータベーススキーマを定義します。

## 4.1. 設計方針

本データベースは、以下の設計方針に基づき、データの永続化を行います。

1.  **ユーザーとチャット、ネットワークの関係**:
    ユーザーは複数のチャットを持つことができます。各チャットセッションは、単一のネットワークに1対1で対応します。

2.  **ノードとエッジの明示的な管理**:
    ネットワークを構成するノードとエッジを明示的に管理します。

3.  **属性の永続化と型別分離**:
    ネットワークの属性（計算結果や元データ由来）は永続的なデータとして扱います。データ型別・要素別に分離したテーブル構造（サブタイプモデル）を採用し、型安全性を確保します。

4.  **属性メタデータの充実化**:
    属性には詳細な説明を付与し、LLMの属性選択精度を向上させます。

## 4.2. ER図

```mermaid
erDiagram
    users ||--o{ chats : "has"
    networks ||--|| chats : "is"
    chats ||--o{ chat_messages : "contains"

    networks ||--o{ nodes : "contains"
    
    networks ||--o{ node_attributes : "defines"
    node_attributes |o--|| node_text_attributes : "is"
    node_attributes |o--|| node_float_attributes : "is"

    nodes ||--o{ node_attribute_values : "has"
    node_attributes ||--o{ node_attribute_values : "value for"
    node_attribute_values |o--|| node_text_attribute_values : "is"
    node_attribute_values |o--|| node_float_attribute_values : "is"

    networks ||--o{ edges : "contains"
    nodes }o--o{ edges : "connects"

    networks ||--o{ edge_attributes : "defines"
    edge_attributes |o--|| edge_text_attributes : "is"
    edge_attributes |o--|| edge_float_attributes : "is"

    edges ||--o{ edge_attribute_values : "has"
    edge_attributes ||--o{ edge_attribute_values : "value for"
    edge_attribute_values |o--|| edge_text_attribute_values : "is"
    edge_attribute_values |o--|| edge_float_attribute_values : "is"

    users {
        INTEGER id PK
        VARCHAR username UK
        VARCHAR hashed_password
    }
    chats {
        INTEGER id PK
        VARCHAR name
        INTEGER user_id FK
        INTEGER network_id FK, UK
    }
    chat_messages {
        INTEGER id PK
        INTEGER chat_id FK
        VARCHAR role
        TEXT content
        JSON meta_data
    }
    networks {
        INTEGER id PK
        VARCHAR name
        INTEGER user_id FK
    }
    nodes {
        INTEGER id PK
        INTEGER network_id FK
        VARCHAR node_id UK
        VARCHAR label
    }
    edges {
        INTEGER id PK
        INTEGER network_id FK
        VARCHAR edge_id UK
        INTEGER source_node_id FK
        INTEGER target_node_id FK
        FLOAT weight
    }
    node_attributes {
        INTEGER id PK
        INTEGER network_id FK
        VARCHAR attribute_name UK
        TEXT description
    }
    node_text_attributes { INTEGER node_attribute_id PK, FK }
    node_float_attributes { INTEGER node_attribute_id PK, FK }
    node_attribute_values {
        INTEGER id PK
        INTEGER node_id FK
        INTEGER attribute_id FK
        UNIQUE(node_id, attribute_id)
    }
    node_text_attribute_values {
        INTEGER node_attribute_value_id PK, FK
        TEXT text_value
    }
    node_float_attribute_values {
        INTEGER node_attribute_value_id PK, FK
        FLOAT float_value
    }
    edge_attributes {
        INTEGER id PK
        INTEGER network_id FK
        VARCHAR attribute_name UK
        TEXT description
    }
    edge_text_attributes { INTEGER edge_attribute_id PK, FK }
    edge_float_attributes { INTEGER edge_attribute_id PK, FK }
    edge_attribute_values {
        INTEGER id PK
        INTEGER edge_id FK
        INTEGER attribute_id FK
        UNIQUE(edge_id, attribute_id)
    }
    edge_text_attribute_values {
        INTEGER edge_attribute_value_id PK, FK
        TEXT text_value
    }
    edge_float_attribute_values {
        INTEGER edge_attribute_value_id PK, FK
        FLOAT float_value
    }
```

### テーブル定義
(テーブル定義のリストはER図とSQLから自明なため省略)

## 4.3. 基本テーブル

### 4.3.1. `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.3.2. `networks`
```sql
CREATE TABLE networks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.3.3. `chats`
```sql
CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL,
    network_id INTEGER NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (network_id) REFERENCES networks(id)
);
```

### 4.3.4. `chat_messages`
```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    meta_data JSON,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (chat_id) REFERENCES chats(id)
);
```

### 4.3.5. `nodes`
```sql
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_id INTEGER NOT NULL,
    node_id VARCHAR(255) NOT NULL,
    label VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (network_id) REFERENCES networks(id),
    UNIQUE(network_id, node_id)
);
```

### 4.3.6. `edges`
```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_id INTEGER NOT NULL,
    edge_id VARCHAR(255) NOT NULL,
    source_node_id INTEGER NOT NULL,
    target_node_id INTEGER NOT NULL,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (network_id) REFERENCES networks(id),
    FOREIGN KEY (source_node_id) REFERENCES nodes(id),
    FOREIGN KEY (target_node_id) REFERENCES nodes(id),
    UNIQUE(network_id, edge_id)
);
```

## 4.4. 属性テーブル（サブタイプ階層）

### `node_attributes` (基底)
```sql
CREATE TABLE node_attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_id INTEGER NOT NULL,
    attribute_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (network_id) REFERENCES networks(id),
    UNIQUE(network_id, attribute_name)
);
```
```sql
CREATE TABLE node_text_attributes (
    node_attribute_id INTEGER PRIMARY KEY,
    FOREIGN KEY (node_attribute_id) REFERENCES node_attributes(id)
);
```
```sql
CREATE TABLE node_float_attributes (
    node_attribute_id INTEGER PRIMARY KEY,
    FOREIGN KEY (node_attribute_id) REFERENCES node_attributes(id)
);
```

### `edge_attributes` (基底)
```sql
CREATE TABLE edge_attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_id INTEGER NOT NULL,
    attribute_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (network_id) REFERENCES networks(id),
    UNIQUE(network_id, attribute_name)
);
```
```sql
CREATE TABLE edge_text_attributes (
    edge_attribute_id INTEGER PRIMARY KEY,
    FOREIGN KEY (edge_attribute_id) REFERENCES edge_attributes(id)
);
```
```sql
CREATE TABLE edge_float_attributes (
    edge_attribute_id INTEGER PRIMARY KEY,
    FOREIGN KEY (edge_attribute_id) REFERENCES edge_attributes(id)
);
```

## 4.5. 属性値テーブル（サブタイプ階層）

### `node_attribute_values` (基底)
```sql
CREATE TABLE node_attribute_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    attribute_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (node_id) REFERENCES nodes(id),
    FOREIGN KEY (attribute_id) REFERENCES node_attributes(id),
    UNIQUE(node_id, attribute_id)
);
```
```sql
CREATE TABLE node_text_attribute_values (
    node_attribute_value_id INTEGER PRIMARY KEY,
    text_value TEXT,
    FOREIGN KEY (node_attribute_value_id) REFERENCES node_attribute_values(id)
);
```
```sql
CREATE TABLE node_float_attribute_values (
    node_attribute_value_id INTEGER PRIMARY KEY,
    float_value FLOAT,
    FOREIGN KEY (node_attribute_value_id) REFERENCES node_attribute_values(id)
);
```

### `edge_attribute_values` (基底)
```sql
CREATE TABLE edge_attribute_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id INTEGER NOT NULL,
    attribute_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (edge_id) REFERENCES edges(id),
    FOREIGN KEY (attribute_id) REFERENCES edge_attributes(id),
    UNIQUE(edge_id, attribute_id)
);
```
```sql
CREATE TABLE edge_text_attribute_values (
    edge_attribute_value_id INTEGER PRIMARY KEY,
    text_value TEXT,
    FOREIGN KEY (edge_attribute_value_id) REFERENCES edge_attribute_values(id)
);
```
```sql
CREATE TABLE edge_float_attribute_values (
    edge_attribute_value_id INTEGER PRIMARY KEY,
    float_value FLOAT,
    FOREIGN KEY (edge_attribute_value_id) REFERENCES edge_attribute_values(id)
);
```
