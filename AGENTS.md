# AI Agents Development Guide

このドキュメントは、生成AIを用いた開発を円滑に進めるためのガイドラインです。

## 開発環境について

### Docker の使用

このプロジェクトでは、開発環境の構築と実行に **Docker** を使用しています。

- バックエンド（API）とフロントエンドはそれぞれDockerコンテナーとして実行されます
- `docker-compose.yml` ファイルでサービスが定義されています
- 環境の一貫性を保つため、Docker環境での開発を推奨します

### Docker Compose コマンドの記法

**重要**: Docker Composeのコマンドは、**スペースを開けて** `docker compose` と記述してください。

#### ✅ 正しい記法

```bash
docker compose up
docker compose down
docker compose build
docker compose ps
docker compose logs
```

#### ❌ 誤った記法（使用しないでください）

```bash
docker-compose up    # ハイフン付きは古い記法です
```

**理由**: Docker Compose V2では、`docker compose`（スペース区切り）が標準のコマンド形式です。`docker-compose`（ハイフン）は古いバージョンの記法であり、環境によっては動作しない可能性があります。

## プロジェクト構成

### 主要なコンポーネント

1. **API** (`/API`)
   - FastAPIベースのバックエンドサーバー
   - ネットワーク解析、認証、LLM統合などの機能を提供
   - Python 3.12+ を使用

2. **frontend** (`/frontend`)
   - React + Viteベースのフロントエンドアプリケーション
   - ネットワーク可視化UI

3. **NetworkXMCP** (`/NetworkXMCP`)
   - NetworkXを使用したグラフ解析MCPサーバー
   - レイアウト計算、中心性指標などの機能を提供

## 開発時の基本コマンド

### サービスの起動

```bash
# すべてのサービスを起動
docker compose up

# バックグラウンドで起動
docker compose up -d

# 特定のサービスのみ起動
docker compose up api
docker compose up frontend
```

### サービスの停止

```bash
# すべてのサービスを停止
docker compose down

# ボリュームも削除して停止
docker compose down -v
```

### ログの確認

```bash
# すべてのサービスのログを表示
docker compose logs

# 特定のサービスのログを表示
docker compose logs api

# リアルタイムでログを追跡
docker compose logs -f
```

### コンテナーの再ビルド

```bash
# すべてのサービスを再ビルド
docker compose build

# キャッシュを使わずに再ビルド
docker compose build --no-cache
```

### サービスの状態確認

```bash
# 実行中のコンテナを確認
docker compose ps
```

## 開発ワークフロー

1. **初回セットアップ**

   ```bash
   # イメージをビルド
   docker compose build

   # サービスを起動
   docker compose up -d
   ```

2. **コード変更後**

   ```bash
   # サービスを再起動（ホットリロードが有効な場合は不要）
   docker compose restart api

   # または、再ビルドが必要な場合
   docker compose up -d --build
   ```

3. **クリーンアップ**

   ```bash
   # コンテナとネットワークを削除
   docker compose down

   # ボリュームも含めて完全にクリーンアップ
   docker compose down -v
   ```

## テストの実行

```bash
# APIのテストを実行
docker compose exec api pytest

# NetworkXMCPのテストを実行
cd NetworkXMCP
python -m pytest
```

## トラブルシューティング

### ポートがすでに使用されている場合

```bash
# 実行中のコンテナーを確認
docker compose ps

# 停止してから再起動
docker compose down
docker compose up
```

### データベースの初期化が必要な場合

```bash
# ボリュームを削除して再起動
docker compose down -v
docker compose up
```

### ログでエラーを確認

```bash
# すべてのログを確認
docker compose logs

# エラーが発生しているサービスのログを詳細に確認
docker compose logs -f api
```

## 注意事項

- コード変更を行う際は、適切なDockerサービスが起動していることを確認してください
- データベースのマイグレーションが必要な場合は、`docker compose down -v` でボリュームを削除してから再起動してください
- 本番環境にデプロイする際は、環境変数やシークレットの管理に注意してください

## 追加リソース

- [Docker Compose ドキュメント](https://docs.docker.com/compose/)
- [プロジェクトREADME](./README.md)
- [LLM Provider ガイド](./LLM_PROVIDER_GUIDE.md)
