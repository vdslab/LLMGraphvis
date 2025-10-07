# Dockerビルド最適化ガイド

このドキュメントでは、プロジェクトのDockerビルド時間を最適化する方法について説明します。

## 実施済みの最適化

### 1. マルチステージビルド

フロントエンドのDockerfileを3ステージ構成に変更：

- **Build Stage**: 本番用ビルドの作成
- **Development Stage**: 開発環境（ホットリロード対応）
- **Production Stage**: Nginx で静的ファイルを配信

### 2. ビルドキャッシュの活用

- **npm キャッシュマウント**: `--mount=type=cache,target=/root/.npm` を使用
- **uv キャッシュマウント**: Python依存関係のキャッシュ（API/NetworkXMCP）
- **レイヤーキャッシング**: `package.json` を先にコピーして依存関係をキャッシュ

### 3. .dockerignore ファイルの整備

各サービスに適切な `.dockerignore` を配置して、不要なファイルのコピーを防止

### 4. cache_from の設定

`docker-compose.yml` にベースイメージのキャッシュ設定を追加

## 開発ワークフロー

### 初回セットアップ

```bash
# BuildKit を有効化（まだの場合）
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# 並列ビルドで高速化
docker compose build --parallel

# サービス起動
docker compose up -d
```

### 日常の開発

```bash
# コード変更時は再ビルド不要（ボリュームマウントで自動反映）
# そのまま開発を続ける

# ログを確認したい場合
docker compose logs -f [service-name]
```

### 依存関係を変更した場合

```bash
# フロントエンド（package.json を変更）
docker compose build frontend
docker compose restart frontend

# API（pyproject.toml または uv.lock を変更）
docker compose build api
docker compose restart api

# NetworkXMCP（pyproject.toml または uv.lock を変更）
docker compose build networkx-mcp
docker compose restart networkx-mcp
```

## 本番ビルド（オプション）

フロントエンドを本番モードでビルドする場合：

```bash
# 本番用の設定ファイルを使用
docker compose -f docker-compose.yml -f docker-compose.prod.yml build frontend

# または、直接 production ステージをターゲット
docker compose build --build-arg TARGET=production frontend
```

## パフォーマンス最適化のヒント

### 1. BuildKit の有効化

`.zshrc` または `.zprofile` に追加：

```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

### 2. Docker Desktop の設定（Mac/Windows）

- **同期されたファイル共有** を有効化（Docker Desktop 4.27+）
  - Settings > Resources > File Sharing
  - プロジェクトディレクトリを選択して「Initialize file sharing」

### 3. WSL 2 の活用（Windows）

- Docker Desktop で WSL 2 バックエンドを有効化
- Settings > General > "Use the WSL 2 based engine"

### 4. リソース割り当て

Docker Desktop のリソース設定を確認：

- Settings > Resources
- CPU、メモリ、ディスクを適切に割り当て

## ビルド時間の目安

| ステージ        | 初回ビルド | キャッシュ有効時 |
| --------------- | ---------- | ---------------- |
| API             | 2-3分      | 10-30秒          |
| NetworkXMCP     | 2-3分      | 10-30秒          |
| Frontend (dev)  | 1-2分      | 5-15秒           |
| Frontend (prod) | 2-3分      | 15-30秒          |

## トラブルシューティング

### キャッシュが効かない場合

```bash
# キャッシュをクリアして再ビルド
docker compose build --no-cache [service-name]

# または、すべてクリーンアップ
docker compose down -v
docker system prune -a
docker compose build --parallel
```

### ビルドが遅い場合

```bash
# ビルドログを詳細表示
docker compose build --progress=plain [service-name]

# BuildKit が有効か確認
echo $DOCKER_BUILDKIT

# Docker Desktop のリソース使用状況を確認
# Docker Desktop > Settings > Resources
```

### ポートが使用されている場合

```bash
# 実行中のコンテナーを確認
docker compose ps

# 停止
docker compose down

# 再起動
docker compose up -d
```

## 参考リンク

- [Docker 公式: React アプリの Docker 化](https://www.docker.com/ja-jp/blog/how-to-dockerize-react-app/)
- [Docker BuildKit ドキュメント](https://docs.docker.com/build/buildkit/)
- [Docker Compose ドキュメント](https://docs.docker.com/compose/)
- [マルチステージビルド](https://docs.docker.com/build/building/multi-stage/)
