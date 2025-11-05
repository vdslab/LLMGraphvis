# 5. 認証フロー

**前提知識レベル:**
- OAuth2, JWTに関する基本的な知識
- シーケンス図の読解能力

**目的:** ユーザーが安全にシステムを利用するための、ユーザー登録およびログインのフローです。

認証後のデータ永続化やグラフ操作については、[6. 主要な処理フローとデータ生成](./6_Core_Workflows.md)を参照してください。

## 5.1. シーケンス図

```mermaid
sequenceDiagram
    autonumber
    participant U as ユーザー
    participant F as Frontend
    participant B as API Service
    participant DB as Database

    %% User Registration & Auto-Login
    U->>F: 新規登録情報入力
    F->>B: POST /auth/register (username, password)
    
    alt 登録成功 (Registration Success)
        B->>DB: ユーザー情報をハッシュ化して保存
        DB-->>B: ユーザー登録成功
        B->>B: JWTを生成
        B-->>F: 200 OK (Set-CookieヘッダーにHttpOnlyのJWTを含める)
        note right of F: 登録後、自動的にログイン状態へ遷移<br/>ブラウザがCookieを自動で保存
    else ユーザー名が既に存在 (Username already exists)
        B->>DB: ユーザー名重複チェック
        DB-->>B: ユーザー名重複エラー
        B-->>F: 409 Conflict ({"detail": "Username already registered"})
        note right of F: ユーザーに具体的なエラーメッセージを表示
    end

    %% User Login
    U->>F: ログイン情報入力
    F->>B: POST /auth/token (username, password)

    alt 認証成功 (Authentication Success)
        B->>DB: ユーザー情報検証
        DB-->>B: 検証成功 (ユーザー情報)
        B->>B: JWTを生成
        B-->>F: 200 OK (Set-CookieヘッダーにHttpOnlyのJWTを含める)
        note right of F: ブラウザがCookieを自動で保存
    else 認証失敗 (Authentication Failure)
        B->>DB: ユーザー情報検証
        DB-->>B: 検証失敗
        B-->>F: 401 Unauthorized
    end
```
