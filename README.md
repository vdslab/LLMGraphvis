# Network Layout Application with Authentication

グラフのレイアウト計算とユーザー認証機能を備えたWebアプリケーション

## プロジェクト構成

このプロジェクトは以下のコンポーネントで構成されています：

- **frontend**: Reactフロントエンド
- **API**: FastAPIバックエンド（認証、ChatGPT連携）
- **NetworkXMCP**: NetworkXを使用したグラフ計算とMCPサーバー
- **db**: PostgreSQLデータベース（ユーザー認証用）

## 機能

- グラフのレイアウト計算（spring, circular, random, spectral）
- ユーザー認証（OAuth2 + JWT + PostgreSQL）
- ChatGPT連携（認証保護）
- Reactフロントエンド

## 始め方

### Dockerでの実行

1.  `.env`ファイルをプロジェクトルートに作成し、必要な環境変数を設定します。`.env.example`をコピーして使用できます。

    ```bash
    cp .env.example .env
    ```

    `.env`ファイル内の`OPENAI_API_KEY`を忘れずに設定してください。

2.  アプリケーションを起動します：

    ```zsh
    # 開発環境（ホットリロード有効）
    docker compose up --build
    ```

3.  アプリケーションにアクセスする：
    *   フロントエンド: http://localhost:3000
    *   バックエンドAPI: http://localhost:8000

### ローカル環境での実行 (Dockerなし)

Dockerを使用せずにローカルで開発環境をセットアップする手順です。

#### 1. 前提条件

-   **Python 3.12+**
-   **Node.js v18+**
-   **PostgreSQL** がローカルにインストールされ、実行中であること。

#### 2. データベースのセットアップ

1.  PostgreSQLに接続し、アプリケーション用のユーザーとデータベースを作成します。

    ```bash
    # psqlに接続
    psql -U postgres

    # ユーザーとデータベースを作成 (パスワードは.envファイルと一致させる)
    CREATE USER postgres WITH PASSWORD 'postgres';
    CREATE DATABASE graphvis;
    GRANT ALL PRIVILEGES ON DATABASE graphvis TO postgres;
    \q
    ```

2.  作成したデータベースにテーブルを初期化します。

    ```bash
    psql -U postgres -d graphvis -f API/init.sql
    ```

#### 3. 環境変数の設定

1.  `.env.example`をコピーして`.env`ファイルを作成します。

    ```bash
    cp .env.example .env
    ```

2.  `.env`ファイルを編集し、ローカル環境に合わせて以下の変数を設定・変更します。

    - `DATABASE_URL`をローカルのPostgreSQLを指すように変更します。
    - `NETWORKX_MCP_URL`をローカルのNetworkXMCPサーバーを指すように追加します。

    ```diff
    - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
    + DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}
    + NETWORKX_MCP_URL=http://localhost:8001
    ```

    `OPENAI_API_KEY`も忘れずに設定してください。

#### 4. バックエンドの起動

1.  **APIサーバー**の依存関係をインストールし、起動します。（ターミナル1）

    ```bash
    # APIディレクトリに移動
    cd API

    # 仮想環境の作成と有効化
    python -m venv .venv
    source .venv/bin/activate

    # 依存関係のインストール
    pip install -e .

    # サーバーの起動
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ```

2.  **NetworkXMCPサーバー**の依存関係をインストールし、起動します。（ターミナル2）

    ```bash
    # NetworkXMCPディレクトリに移動
    cd NetworkXMCP

    # 仮想環境の作成と有効化
    python -m venv .venv
    source .venv/bin/activate

    # 依存関係のインストール
    pip install -e .

    # サーバーの起動
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload
    ```

#### 5. フロントエンドの起動

1.  **フロントエンド**の依存関係をインストールし、開発サーバーを起動します。（ターミナル3）

    ```bash
    # frontendディレクトリに移動
    cd frontend

    # 依存関係のインストール
    npm install

    # 開発サーバーの起動
    npm run dev
    ```

#### 6. アプリケーションへのアクセス

すべてのサービスが起動したら、以下のURLにアクセスします。

-   **フロントエンド**: http://localhost:3000
-   **バックエンドAPI**: http://localhost:8000
-   **NetworkXMCP API**: http://localhost:8001

これで、Dockerなしで開発環境が整いました。

## 認証の使い方

### 1. ユーザー登録

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'
```

### 2. トークン取得

```bash
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"
```

レスポンス：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. 保護されたエンドポイントへのアクセス

```bash
curl -X POST "http://localhost:8000/chatgpt/generate" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, ChatGPT!"}'
```

## API エンドポイント

- `POST /auth/register` - 新規ユーザー登録
- `POST /auth/token` - アクセストークン取得
- `GET /auth/users/me` - 現在のユーザー情報取得
- `POST /chatgpt/generate` - ChatGPT応答生成（認証必須）
- `POST /chatgpt/recommend-layout` - ネットワーク特性に基づいた最適なレイアウトアルゴリズムの推薦（認証必須）
- `POST /network/layout` - グラフレイアウト計算

## NetworkXMCP

NetworkXMCPは、NetworkXを使用したグラフ計算とMCPサーバーを提供するコンポーネントです。依存関係は`pyproject.toml`で管理されています。詳細は[NetworkXMCP/README.md](NetworkXMCP/README.md)を参照してください。

## サポートされているレイアウトアルゴリズム

NetworkXの以下のレイアウトアルゴリズムをサポートしています：

1. **spring** - バネモデルに基づくレイアウト
2. **circular** - 円形配置
3. **random** - ランダム配置
4. **spectral** - スペクトル分解に基づくレイアウト
5. **shell** - 同心円状配置
6. **spiral** - 螺旋状配置
7. **planar** - 平面グラフ用レイアウト
8. **kamada_kawai** - Kamada-Kawaiアルゴリズム
9. **fruchterman_reingold** - Fruchterman-Reingoldアルゴリズム
10. **bipartite** - 二部グラフ用レイアウト
11. **multipartite** - 多部グラフ用レイアウト

## レイアウト推薦機能の使用例

```bash
curl -X POST "http://localhost:8000/chatgpt/recommend-layout" \
  -H "Authorization: Bearer {取得したトークン}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "ソーシャルネットワークで、約500ノードと2000エッジがあります。コミュニティ構造が存在します。",
    "purpose": "コミュニティ構造を視覚化したいです。"
  }'
```

レスポンス例：

```json
{
  "recommended_layout": "fruchterman_reingold",
  "explanation": "Fruchterman-Reingoldアルゴリズムは、大規模なネットワークのコミュニティ構造を視覚化するのに適しています。このアルゴリズムは力学モデルを使用し、ノードの分布を均等にしながらクラスター構造を保持します。",
  "recommended_parameters": {
    "k": 0.5,
    "iterations": 50
  }
}
```
