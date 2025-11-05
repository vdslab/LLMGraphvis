# 5. 認証フロー

**前提知識レベル:**
- OAuth2, JWTに関する基本的な知識
- シーケンス図の読解能力

**目的:** ユーザーが安全にシステムを利用するための、ユーザー登録およびログインのフローです。

認証後のデータ永続化やグラフ操作については、[6. 主要な処理フローとデータ生成](./6_Core_Workflows.md)を参照してください。

## 5.1. フローチャート

### 新規登録フロー

```mermaid
graph TD
    A[ユーザーが登録情報を入力] --> B{API: /auth/register};
    B --> C{ユーザー名が既に存在するか？};
    C -- Yes --> D[409 Conflictエラーを返す];
    C -- No --> E[パスワードをハッシュ化];
    E --> F[ユーザー情報をDBに保存];
    F --> G[JWTを生成];
    G --> H[HttpOnly Cookieとして<br/>JWTをセットし、<br/>200 OKを返す];
    H --> I[ログイン状態に遷移];

    style A fill:#d1e0ff,stroke:#333,stroke-width:2px
    style D fill:#ffcdd2,stroke:#333,stroke-width:2px
    style I fill:#caffbf,stroke:#333,stroke-width:2px
```

### ログインフロー

```mermaid
graph TD
    A[ユーザーがログイン情報を入力] --> B{API: /auth/token};
    B --> C{ユーザー情報が正しいか？};
    C -- Yes --> E[JWTを生成];
    C -- No --> D[401 Unauthorizedエラーを返す];
    E --> F[HttpOnly Cookieとして<br/>JWTをセットし、<br/>200 OKを返す];
    F --> G[ログイン状態に遷移];

    style A fill:#d1e0ff,stroke:#333,stroke-width:2px
    style D fill:#ffcdd2,stroke:#333,stroke-width:2px
    style G fill:#caffbf,stroke:#333,stroke-width:2px
```
