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

### 5.1.2. ログインフロー

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

### 5.1.3. ログアウトフロー

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend

    User->>Frontend: ログアウトボタンをクリック
    Frontend->>Backend: POST /auth/logout
    Backend->>Backend: Cookie削除 (Set-Cookie: access_token=; Max-Age=0)
    Backend-->>Frontend: 200 OK
    Frontend->>User: ログイン画面に遷移
```

ログアウトは Cookie を消すだけである。Bearer トークンは期限かパスワード変更まで有効である。

### 5.1.4. パスワード変更フロー

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Database

    User->>Frontend: 現在と新しいパスワードを入力
    Frontend->>Backend: POST /auth/change-password
    alt 現在のパスワードが一致
        Backend->>Database: パスワードハッシュを更新し token_version を +1
        Backend->>Backend: 新しい ver を含む JWT を生成
        Backend-->>Frontend: 200 OK (Set-Cookie に新しい JWT)
        Frontend->>User: 変更完了を表示（この端末はログインのまま）
    else 不一致
        Backend-->>Frontend: 400 Bad Request
    end
```

## 5.2. トークンの版

JWT は `sub`（ユーザー名）と `ver`（発行時の `token_version`）を持つ。認証時に
`ver` がユーザーの現在の版と一致しなければ拒否する。パスワード変更で版を上げると、
それ以前に発行したトークンはすべて無効になり、他の端末はログアウトされる。
失効リストを持たずに済む代わりに、1 つのセッションだけを失効させることはできない。
`ver` のない旧トークンは版 0 とみなす（ADR [0026](../4_Decisions/0026-user-settings.md)）。
