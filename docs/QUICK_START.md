# クイックスタートガイド

LLMGraphvisプロジェクトの迅速な起動方法を説明します。このプロジェクトは、ネットワーク可視化、AI統合、ユーザー認証機能を備えたWebアプリケーションです。

## 🚀 はじめての起動（初回のみ時間がかかります）

### 前提条件

- DockerとDocker Composeがインストールされていること
- Gitがインストールされていること

### 環境設定

1. **環境ファイルの作成**

   ```bash
   # プロジェクトルートで実行
   cp .env.example .env
   ```

2. **APIキーの設定**

   `.env`ファイルを編集して、必要なAPIキーを設定してください：
   
   ```bash
   # LLM Provider（google または openai）
   LLM_PROVIDER=google
   GOOGLE_API_KEY="your_google_api_key"
   # または
   # OPENAI_API_KEY="your_openai_api_key"
   ```

### 初回ビルド（約10-20分）

```bash
# BuildKitを有効化（推奨）
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# すべてのサービスをビルド
docker compose build

# サービス起動
docker compose up -d
```

**注意**: 初回はベースイメージのダウンロードに時間がかかります（ネットワーク速度によります）

### アクセス確認

サービスが起動したら、以下のURLでアクセスできます：

- **フロントエンド**: http://localhost:3000
- **API**: http://localhost:8000
- **NetworkXMCP**: http://localhost:8001
- **API ドキュメント**: http://localhost:8000/docs
- **NetworkXMCP ドキュメント**: http://localhost:8001/docs

## ⚡ 2回目以降の起動（数秒で完了）

### コード変更後の起動（再ビルド不要！）

```bash
# サービスを再起動するだけ
docker compose restart

# または、停止してから起動
docker compose down
docker compose up -d
```

**理由**: ボリュームマウントと`--reload`オプションにより、コード変更は自動的に反映されます。

## 🔄 再ビルドが必要な場合

### 依存関係を変更した場合のみ

#### API/NetworkXMCPの依存関係変更（pyproject.toml, uv.lock）

```bash
# 特定のサービスだけ再ビルド
docker compose build api
docker compose restart api

# または
docker compose build networkx-mcp
docker compose restart networkx-mcp
```

#### フロントエンドの依存関係変更（package.json）

```bash
docker compose build frontend
docker compose restart frontend
```

## 📊 ビルド時間の目安

| 状況                            | 時間     | 説明                         |
| ------------------------------- | -------- | ---------------------------- |
| **初回ビルド**                  | 10-20分  | ベースイメージのダウンロード |
| **2回目以降（キャッシュ有効）** | 10-30秒  | レイヤーキャッシュを活用     |
| **コード変更後**                | **0秒**  | 再ビルド不要！               |
| **依存関係変更後**              | 30秒-2分 | 差分のみ再インストール       |

## 🛠️ 開発ワークフロー

### 通常の開発サイクル

1. **コードを編集**
   - API、フロントエンド、NetworkXMCPのファイルを編集

2. **変更を確認**

   ```bash
   # 各サービスのログを確認
   docker compose logs -f api
   docker compose logs -f frontend
   docker compose logs -f networkx-mcp
   docker compose logs -f db
   ```

3. **サービスを再起動（必要な場合のみ）**
   ```bash
   # 特定のサービスを再起動
   docker compose restart api
   docker compose restart frontend
   docker compose restart networkx-mcp
   ```

**重要**: ホットリロードが有効なので、通常は再起動も不要です！

### 認証機能の利用

1. **ユーザー登録**
   ```bash
   curl -X POST "http://localhost:8000/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "password123"}'
   ```

2. **トークン取得**
   ```bash
   curl -X POST "http://localhost:8000/auth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=password123"
   ```

3. **LLM機能の使用**
   ```bash
   curl -X POST "http://localhost:8000/chatgpt/generate" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "ネットワーク可視化について教えて"}'
   ```

### トラブルシューティング

#### キャッシュをクリアして完全再ビルド

```bash
# すべてをクリーンアップ
docker compose down -v
docker system prune -a

# 再ビルド
docker compose build --parallel --no-cache
docker compose up -d
```

#### 特定のサービスだけ再起動

```bash
docker compose restart frontend
docker compose restart api
docker compose restart networkx-mcp
```

#### ログを確認

```bash
# すべてのサービス
docker compose logs -f

# 特定のサービス
docker compose logs -f api
```

## 💡 ビルドを高速化するコツ

### 1. BuildKitを常に有効化

`.zshrc` に追加：

```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

### 2. Docker Desktopの設定最適化

- **Resources** → CPUとメモリを増やす
- **同期されたファイル共有**を有効化（Docker Desktop 4.27+）

### 3. 不要なイメージを定期的に削除

```bash
# 未使用のイメージを削除
docker image prune -a

# すべてをクリーンアップ（注意）
docker system prune -a --volumes
```

## 🎯 よくある質問

### Q: なぜ初回ビルドに時間がかかるの？

A: Dockerのベースイメージ（Python、Node.js、PostgreSQL）をダウンロードする必要があるためです。2回目以降はキャッシュされます。

### Q: コードを変更したらビルドが必要？

A: **不要です！** ボリュームマウントとホットリロードにより、変更は自動的に反映されます。

### Q: いつ再ビルドが必要？

A: 以下の場合のみ：

- `package.json`を変更した（フロントエンド）
- `pyproject.toml`または`uv.lock`を変更した（API/NetworkXMCP）
- Dockerfileを変更した
- 新しい依存関係を追加した

### Q: サービスが起動しない場合は？

A: 以下を確認してください：

1. ポートが他のプロセスで使用されていないか（3000, 8000, 8001, 5432）
2. `.env`ファイルが正しく設定されているか
3. Dockerに十分なメモリが割り当てられているか

### Q: データベース接続エラーが発生する場合は？

A: データベースの初期化を待つか、再起動してください：

```bash
docker compose down -v
docker compose up -d
```

### Q: ビルドが遅すぎる！

A:

1. ネットワーク接続を確認
2. Docker Desktopのリソース割り当てを増やす
3. BuildKitを有効化する
4. 不要なDockerイメージを削除: `docker system prune`

## 📚 関連ドキュメント

- [AGENTS.md](../AGENTS.md) - AI Agentsのための開発ガイド
- [LLM_PROVIDER_GUIDE.md](./LLM_PROVIDER_GUIDE.md) - LLMプロバイダー設定ガイド
- [TESTING_GUIDE.md](./TESTING_GUIDE.md) - テスト実行ガイド
- [NetworkXMCP/README.md](../NetworkXMCP/README.md) - NetworkXMCPサーバーの詳細
- [API/README_network_layout.md](../API/README_network_layout.md) - ネットワークレイアウト機能

## 🚦 ステータス確認

```bash
# 実行中のコンテナーを確認
docker compose ps

# 全サービスの状態
docker compose logs --tail=50

# 個別サービスの状態
docker compose logs api
docker compose logs frontend
docker compose logs networkx-mcp
docker compose logs db

# リソース使用状況
docker stats
```
