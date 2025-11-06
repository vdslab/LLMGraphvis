# 5. 認証フロー

**前提知識レベル:**
- OAuth2, JWTに関する基本的な知識
- シーケンス図の読解能力

**目的:** ユーザーが安全にシステムを利用するための、ユーザー登録およびログインのフローです。

認証後のデータ永続化やグラフ操作については、[6. 主要な処理フローとデータ生成](./6_Core_Workflows.md)を参照してください。

## 5.1. シーケンス図

### 5.1.1. 新規ユーザー登録フロー

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Database

    User->>Frontend: ユーザー名とパスワードを入力し、登録ボタンをクリック
    Frontend->>Backend: POST /auth/register (ユーザー情報)
    Backend->>Database: SELECT ユーザー名
    alt ユーザー名が既に存在
        Database-->>Backend: ユーザーが存在
        Backend-->>Frontend: 409 Conflict
        Frontend-->>User: エラーメッセージを表示
    else ユーザー名がユニーク
        Database-->>Backend: ユーザーが存在しない
        Backend->>Backend: パスワードをハッシュ化
        Backend->>Database: INSERT ユーザー情報
        Database-->>Backend: 登録成功
        Backend->>Backend: JWTを生成
        Backend-->>Frontend: 200 OK (Set-CookieヘッダーにHttpOnlyのJWT)
        Frontend->>User: ログイン後の画面に遷移
    end
```

### 5.1.2. ログインンフロー

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Database

    User->>Frontend: ユーザー名とパスワードを入力し、ログインボタンをクリック
    Frontend->>Backend: POST /auth/token (ユーザー情報)
    Backend->>Database: SELECT ユーザー情報
    alt 認証成功
        Database-->>Backend: ユーザー情報
        Backend->>Backend: パスワードハッシュを比較
        Backend->>Backend: JWTを生成
        Backend-->>Frontend: 200 OK (Set-CookieヘッダーにHttpOnlyのJWT)
        Frontend->>User: ログイン後の画面に遷移
    else 認証失敗
        Database-->>Backend: ユーザーが存在しない or パスワード不一致
        Backend-->>Frontend: 401 Unauthorized
        Frontend-->>User: エラーメッセージを表示
    end
```
