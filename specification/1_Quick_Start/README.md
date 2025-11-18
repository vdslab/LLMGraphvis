# 開発者向けクイックスタートガイド

**前提知識レベル:**

- 基本的なGit操作
- Node.js/npm (またはyarn)
- Python 3.12+
- Dockerの基礎知識
- React, FastAPIに関する基本的な開発経験

## 1. 概要

このガイドは、開発者がGraphVisAgentのローカル開発環境をセットアップし、アプリケーションを起動するまでの手順を説明します。

本システムは、ローカルで実行される各サービス（フロントエンド、バックエンド、計算サービス）と、Dockerで実行されるデータベース（PostgreSQL）で構成されます。

**注意:** このドキュメントリポジトリ (`GraphVisAgent-docs`) は仕様書のみを管理しています。実際のソースコードは本体の `LLMGraphvis` リポジトリにあります。以下の手順は、本体リポジトリのルートディレクトリで実行することを想定しています。

## 2. 環境構築手順

### ステップ1: リポジトリのクローンと環境変数の設定

```bash
git clone https://github.com/your-repo/LLMGraphvis.git
cd LLMGraphvis

# 環境変数のテンプレートをコピー
cp .env.example .env
```
`.env`ファイルを開き、必要に応じて内容を編集してください。（通常はデフォルトのままで動作します）

### ステップ2: データベースの起動

Dockerを使用してPostgreSQLデータベースを起動します。

```bash
docker-compose up -d postgres
```

### ステップ3: 依存関係のインストール

各サービスのディレクトリに移動し、必要なパッケージをインストールします。

```bash
# バックエンド
cd backend
pip install -r requirements.txt
cd ..

# ネットワーク計算サービス
cd networkx-api
pip install -r requirements.txt
cd ..

# フロントエンド
cd frontend
npm install
cd ..
```

### ステップ4: サービスの起動

各サービスを個別のターミナルで起動します。

```bash
# ターミナル1: バックエンドを起動
cd backend
uvicorn main:app --reload --port 8000

# ターミナル2: ネットワーク計算サービスを起動
cd networkx-api
uvicorn main:app --reload --port 8001

# ターミナル3: フロントエンドを起動
cd frontend
npm run dev
```

### ステップ5: アプリケーションへのアクセス

各サービスが正常に起動したら、Webブラウザで以下のURLにアクセスします。

- **フロントエンド (アプリケーション本体):** `http://localhost:5173`
- **バックエンドAPIドキュメント (Swagger UI):** `http://localhost:8000/docs`
- **NetworkXAPIドキュメント (Swagger UI):** `http://localhost:8001/docs`

---

_これでローカル開発環境の準備は完了です。各コンポーネントのより詳細なアーキテクチャやAPI仕様については、[詳細技術仕様](../2_Technical_Details/)を参照してください。_
