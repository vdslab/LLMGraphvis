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

**理由**: Docker Compose V2では、`docker compose`（スペース区切り）が標準のコマンド形式です。`docker-compose`（ハイフン）は古いバージョンの記法であり、環境によっては動作しない可能性があります。現在の開発環境で確認されているバージョンは `Docker Compose version v2.40.0-desktop.1` であり、このバージョンでは `docker compose` とスペースを開ける必要があります。

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

## MCPツールの活用

このプロジェクトでは、開発の品質と効率を向上させるために、以下のModel Context Protocol (MCP) ツールを積極的に活用してください。

### Context 7 - 最新ドキュメントの確認

**Context 7** を使用して、使用しているライブラリやフレームワークの最新のドキュメントを常に確認してください。

#### 使用する場面

- 新しいライブラリを導入する際
- 既存のAPIの使用方法を確認する際
- ベストプラクティスを調べる際
- バージョンアップ時の変更点を確認する際

#### 主要な対象技術

- **React**: コンポーネント設計、Hooks、状態管理
- **FastAPI**: エンドポイント設計、依存性注入、バリデーション
- **NetworkX**: グラフアルゴリズム、レイアウト計算
- **Docker**: コンテナー設定、マルチステージビルド
- **Vite**: ビルド設定、プラグイン設定

#### 使用例

```
Context 7を使用して、React 18の最新のuseEffectのベストプラクティスを確認してください
FastAPIの最新のWebSocket実装方法について、Context 7で調べてください
```

### Chrome DevTools MCP - 実装検証

**Chrome DevTools MCP** を使用して、フロントエンドの実装が適切に行われているかを確認してください。

#### 使用する場面

- レスポンシブデザインの確認
- パフォーマンスの測定と最適化
- ネットワークリクエストの監視
- JavaScriptエラーのデバッグ
- アクセシビリティの検証

#### 主要な検証項目

**レスポンシブデザイン**

```bash
# 異なる画面サイズでのレイアウト確認
- デスクトップ（1920x1080）
- タブレット（768x1024）
- モバイル（375x667）
```

**パフォーマンス**

```bash
# Core Web Vitalsの測定
- Largest Contentful Paint (LCP)
- First Input Delay (FID)
- Cumulative Layout Shift (CLS)
```

**ネットワーク監視**

```bash
# API通信の確認
- リクエスト/レスポンス時間
- エラーハンドリング
- キャッシュ戦略
```

#### 検証ワークフロー

1. **開発サーバーの起動**

   ```bash
   docker compose up frontend
   ```

2. **Chrome DevToolsでの検証**
   - Elements: DOM構造とCSS
   - Console: JavaScriptエラー
   - Network: API通信
   - Performance: パフォーマンス測定
   - Lighthouse: 総合的な品質評価

3. **問題の特定と修正**
   - 特定された問題をドキュメント化
   - 修正方針の決定
   - 修正後の再検証

#### 継続的な品質管理

- **プルリクエスト前**: 必ずChrome DevToolsで動作確認
- **新機能実装時**: パフォーマンス影響の測定
- **リファクタリング後**: 機能の動作確認
- **定期的**: アクセシビリティ監査の実施

### MCP活用のベストプラクティス

1. **コーディング前**: Context 7で最新情報を確認
2. **実装中**: 適宜ドキュメントを参照
3. **実装後**: Chrome DevToolsで動作・パフォーマンスを検証
4. **リリース前**: 総合的な品質チェック

これらのツールを活用することで、常に最新のベストプラクティスに従った高品質な実装を維持できます。

## 追加リソース

- [Docker Compose ドキュメント](https://docs.docker.com/compose/)
- [プロジェクトREADME](./README.md)
- [LLM Provider ガイド](./LLM_PROVIDER_GUIDE.md)
