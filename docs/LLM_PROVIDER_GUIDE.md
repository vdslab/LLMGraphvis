# LLM Provider Configuration Guide

このアプリケーションは、チャット機能とネットワーク分析機能に複数の大規模言語モデル（LLM）プロバイダーをサポートしています。環境変数を設定することで、**Google Gemini**と**OpenAI**を切り替えることができます。

## サポートされている機能

- **チャット機能**: ユーザーとの対話的なやりとり
- **ネットワークレイアウト推薦**: ネットワーク特性に基づく最適なレイアウトアルゴリズムの提案
- **グラフ解析**: ネットワーク構造の分析と可視化の最適化

## 設定手順

以下の手順にしたがってLLMプロバイダーとAPIキーを設定してください：

### 1. 環境ファイルの作成

プロジェクトルートディレクトリに、`.env.example`という名前のテンプレートファイルがあります。

まず、このファイルをコピーして`.env`という名前にします：

```bash
cp .env.example .env
```

### 2. `.env`ファイルの編集

新しく作成された`.env`ファイルをテキストエディターで開きます。以下のような内容になっています：

```
# LLM Provider Settings
# "google" または "openai" を選択
LLM_PROVIDER=google

# API Keys
# APIキーをここに追加してください。これらはアプリケーション環境に読み込まれます。
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"

# OpenAIモデルを指定することも可能です（オプション）
# OPENAI_MODEL="gpt-4o"

# Database configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=graphvis
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

# JWT settings
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 3. 変数の設定

`.env`ファイル内の変数をニーズに合わせて変更してください：

- **`LLM_PROVIDER`**:
  - Google Geminiを使用する場合は`google`に設定
  - OpenAIのモデル（例：GPT-4o）を使用する場合は`openai`に設定

- **`GOOGLE_API_KEY`**:
  - `google`を使用する場合、[Google AI Studio](https://aistudio.google.com/app/apikey)から取得したAPIキーを貼り付けてください。

- **`OPENAI_API_KEY`**:
  - `openai`を使用する場合、[OpenAI Platform](https://platform.openai.com/api-keys)から取得したAPIキーを貼り付けてください。

- **`OPENAI_MODEL`**（オプション）:
  - `openai`を使用する場合、コメントアウトを解除してモデル名を指定できます。例：`OPENAI_MODEL="gpt-4o"`。コメントアウトしたままの場合、デフォルトで`gpt-4o`が使用されます。

- **その他の設定**:
  - データベース接続情報（`POSTGRES_*`、`DATABASE_URL`）
  - JWT認証設定（`SECRET_KEY`、`ALGORITHM`、`ACCESS_TOKEN_EXPIRE_MINUTES`）

**重要**: `.env`ファイルは`.gitignore`に記載されており、Gitリポジトリにコミットされません。これはAPIキーを保護するためのセキュリティ対策です。

### 4. アプリケーションの再起動

`.env`ファイルを変更・保存した後、変更を有効にするためにDockerコンテナーを再起動する必要があります。

プロジェクトルートでターミナルで以下のコマンドを実行してください：

```bash
docker compose down
docker compose up -d
```

これで、設定したLLMプロバイダーでアプリケーションが実行されます。

## 機能の利用方法

### チャット機能

```bash
# 認証トークンを取得
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"

# LLMチャット機能を使用
curl -X POST "http://localhost:8000/chatgpt/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "ネットワーク分析について教えてください"}'
```

### レイアウト推薦機能

```bash
curl -X POST "http://localhost:8000/chatgpt/recommend-layout" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "ソーシャルネットワークで、約500ノードと2000エッジがあります。",
    "purpose": "コミュニティ構造を可視化したいです。"
  }'
```

## トラブルシューティング

### よくある問題

1. **APIキーエラー**: APIキーが正しく設定されているか確認してください
2. **プロバイダー切り替えエラー**: `LLM_PROVIDER`の値が`google`または`openai`であることを確認してください
3. **認証エラー**: JWTトークンが有効であることを確認してください

### ログの確認

```bash
# APIサービスのログを確認
docker compose logs api

# エラーの詳細を確認
docker compose logs api | grep -i error
```
