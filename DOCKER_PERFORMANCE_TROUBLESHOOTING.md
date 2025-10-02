# Dockerビルドが遅い場合のトラブルシューティング

## 🐌 問題: Dockerのダウンロードだけが異常に遅い

インターネット接続は正常なのに、Dockerのイメージダウンロードだけが遅い場合の対処法

## 🔧 解決策

### 1. Docker Desktopのリソース設定を確認

#### macOS

1. Docker Desktop を開く
2. Settings (⚙️) → Resources
3. 以下を増やす：
   - **CPU**: 4コア以上推奨
   - **Memory**: 8GB以上推奨
   - **Disk**: 十分な空き容量

#### 設定例

```
CPU: 4-6 コア
Memory: 8-12 GB
Swap: 2-4 GB
Disk image size: 60GB以上
```

### 2. Dockerのレジストリミラーを設定（推奨）

#### macOS の場合

1. Docker Desktop → Settings → Docker Engine
2. 以下のJSON設定を追加：

```json
{
  "registry-mirrors": ["https://mirror.gcr.io"],
  "max-concurrent-downloads": 10,
  "max-download-attempts": 5
}
```

3. "Apply & Restart" をクリック

### 3. VPNやプロキシの確認

VPNを使用している場合：

```bash
# VPNを一時的に無効化してテスト
# または、Docker Desktop → Settings → Resources → Proxies
```

### 4. Dockerのネットワーク設定を最適化

#### ~/.docker/daemon.json を作成/編集

```bash
# ファイルを作成
cat > ~/.docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.gcr.io"
  ],
  "max-concurrent-downloads": 10,
  "max-download-attempts": 5,
  "debug": false,
  "experimental": false
}
EOF
```

その後、Docker Desktopを再起動

### 5. DNSの設定を変更

Docker DesktopのDNS設定を変更：

1. Docker Desktop → Settings → Docker Engine
2. 以下を追加：

```json
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}
```

### 6. ベースイメージを事前にプル

ビルド前にベースイメージを手動でダウンロード：

```bash
# ベースイメージを事前にダウンロード
docker pull ghcr.io/astral-sh/uv:python3.12-bookworm-slim
docker pull node:20-alpine
docker pull postgres:15

# その後、ビルド
docker compose build --parallel
```

### 7. 別のレジストリを使用

GitHub Container Registryが遅い場合、Docker Hubのイメージを使用：

#### API と NetworkXMCP の Dockerfile を変更

現在：

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
```

代替案1（Docker Hub）：

```dockerfile
FROM python:3.12-slim-bookworm

# uvをインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
```

代替案2（公式Pythonイメージ + 手動uv）：

```dockerfile
FROM python:3.12-slim-bookworm

# uvをインストール
RUN pip install uv
```

### 8. Docker Desktopの完全再起動

```bash
# Docker Desktopを完全に終了
# 1. Docker Desktop を終了
# 2. ターミナルで実行：

# Dockerプロセスを強制終了
killall Docker

# Dockerのキャッシュをクリア
rm -rf ~/Library/Containers/com.docker.docker/Data/vms/0/data

# Docker Desktopを再起動
open -a Docker
```

**注意**: キャッシュクリアはすべてのイメージを削除します

### 9. 診断コマンド

#### ネットワーク速度をテスト

```bash
# Docker経由でダウンロード速度をテスト
time docker pull hello-world

# 通常のダウンロード速度をテスト
time curl -o /dev/null https://mirror.gcr.io/v2/

# DNSの応答時間
nslookup ghcr.io
nslookup docker.io
```

#### Docker Desktopの診断

```bash
# Dockerの情報を確認
docker info

# ネットワーク設定を確認
docker network ls
docker network inspect bridge
```

### 10. BuildKitの最適化設定

`.zshrc` に以下を追加：

```bash
# BuildKitを有効化
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# BuildKitの並列ダウンロード数を増やす
export BUILDKIT_PROGRESS=plain
```

ターミナルを再起動するか：

```bash
source ~/.zshrc
```

## 🎯 推奨される対処順序

### クイックフィックス（5分）

1. **Docker Desktopを再起動**
2. **リソース設定を確認**（CPU 4コア、メモリ8GB以上）
3. **ベースイメージを事前にプル**

```bash
docker pull ghcr.io/astral-sh/uv:python3.12-bookworm-slim
docker pull node:20-alpine
docker compose build --parallel
```

### 中期的な対策（15分）

4. **レジストリミラーを設定**
5. **DNS設定を変更**（8.8.8.8を使用）
6. **max-concurrent-downloadsを10に設定**

### 根本的な解決（30分）

7. **VPN/プロキシの設定を確認**
8. **ベースイメージを変更**（ghcr.io → Docker Hub）
9. **Docker Desktopの完全リセット**

## 📊 期待される改善

| 対策               | 期待される改善             |
| ------------------ | -------------------------- |
| リソース増加       | 10-20%高速化               |
| レジストリミラー   | 30-50%高速化               |
| 事前プル           | 初回ビルドのみ効果         |
| DNS変更            | 20-30%高速化               |
| ベースイメージ変更 | 50-70%高速化（最も効果的） |

## 🚀 最も効果的な方法

### ベースイメージを事前にダウンロード

```bash
# 1. ベースイメージを事前にダウンロード（バックグラウンドで実行）
docker pull ghcr.io/astral-sh/uv:python3.12-bookworm-slim &
docker pull node:20-alpine &
docker pull postgres:15 &

# 2. ダウンロード完了を待つ
wait

# 3. ビルド（キャッシュが効いて高速）
docker compose build --parallel
```

### 並列ダウンロードを有効化

Docker Desktop → Settings → Docker Engine：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 10
}
```

## 💡 その他のヒント

### キャッシュを確認

```bash
# Dockerのディスク使用量を確認
docker system df

# 不要なキャッシュを削除
docker builder prune -a
```

### ビルドログを詳細表示

```bash
# 詳細なログでどこが遅いか確認
BUILDKIT_PROGRESS=plain docker compose build
```

## 📞 それでも遅い場合

以下の情報を確認してください：

```bash
# ネットワーク速度
speedtest-cli  # または https://fast.com

# Docker Desktop バージョン
docker --version

# Docker Desktop の診断
# Docker Desktop → Troubleshoot → Run diagnostics
```

診断結果を添えて、Docker Desktopのサポートに問い合わせることをお勧めします。
