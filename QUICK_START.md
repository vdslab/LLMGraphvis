# クイックスタートガイド

## 🚀 初めての起動（初回のみ時間がかかります）

### 初回ビルド（約10-20分）

```bash
# BuildKitを有効化
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# 並列ビルド
docker compose build --parallel

# サービス起動
docker compose up -d
```

**注意**: 初回はベースイメージのダウンロードに時間がかかります（ネットワーク速度によります）

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
   # ログを確認
   docker compose logs -f api
   docker compose logs -f frontend
   docker compose logs -f networkx-mcp
   ```

3. **サービスを再起動（必要な場合のみ）**
   ```bash
   docker compose restart api
   ```

**重要**: ホットリロードが有効なので、通常は再起動も不要です！

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

A: Dockerのベースイメージ（約100-200MB）をダウンロードする必要があるためです。2回目以降はキャッシュされます。

### Q: コードを変更したらビルドが必要？

A: **不要です！** ボリュームマウントとホットリロードにより、変更は自動的に反映されます。

### Q: いつ再ビルドが必要？

A: 以下の場合のみ：

- `package.json`を変更した（フロントエンド）
- `pyproject.toml`または`uv.lock`を変更した（API/NetworkXMCP）
- Dockerfileを変更した

### Q: ビルドが遅すぎる！

A:

1. ネットワーク接続を確認
2. Docker Desktopのリソース割り当てを増やす
3. `docker system prune`で不要なキャッシュを削除
4. 2回目以降のビルドは高速になります

## 📚 関連ドキュメント

- [BUILD_OPTIMIZATION.md](./BUILD_OPTIMIZATION.md) - ビルド最適化の詳細
- [AGENTS.md](./AGENTS.md) - 開発環境ガイド
- [NetworkXMCP/DEPENDENCY_ANALYSIS.md](./NetworkXMCP/DEPENDENCY_ANALYSIS.md) - 依存関係分析

## 🚦 ステータス確認

```bash
# 実行中のコンテナーを確認
docker compose ps

# サービスの状態
docker compose logs --tail=50

# リソース使用状況
docker stats
```
