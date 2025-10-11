# LLMGraphvis - AI-Powered Network Visualization Platform

AI統合とユーザー認証機能を備えた高度なネットワーク可視化・分析Webアプリケーション

## ✨ 主な機能

- 🔗 **ネットワーク可視化**: 11種類のレイアウトアルゴリズムをサポート
- 🤖 **AI統合**: Google Gemini/OpenAIによる智的なレイアウト推薦
- 🔐 **認証システム**: OAuth2+JWT+PostgreSQLによる安全なユーザー管理
- ⚡ **高性能**: NetworkXMCP Serverによる分散グラフ処理
- 🎯 **MCP対応**: Model Context Protocol (FastMCP 2.0)によるLLM統合
- 🎨 **モダンUI**: React+Viteによるレスポンシブフロントエンド

## 🏗️ アーキテクチャ

このプロジェクトは以下のマイクロサービスで構成されています：

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Server    │    │ NetworkXMCP     │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (FastMCP)     │
│   Port: 3000    │    │   Port: 8000    │    │   Port: 8001    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │   PostgreSQL    │
                        │   Port: 5432    │
                        └─────────────────┘
```

### コンポーネント詳細

- **Frontend**: React+ViteによるSPA（Single Page Application）
- **API**: FastAPIバックエンド（認証、LLM統合、ネットワーク管理）
- **NetworkXMCP**: NetworkX+FastMCP 2.0による分散グラフ処理サーバー
- **Database**: PostgreSQLによるユーザー認証とセッション管理

## 🚀 クイックスタート

### 前提条件

- DockerとDocker Compose
- Git

### 1. リポジトリのクローン

```bash
git clone https://github.com/vdslab/LLMGraphvis.git
cd LLMGraphvis
```

### 2. 環境設定

```bash
# 環境変数ファイルを作成
cp .env.example .env

# .envファイルを編集してAPIキーを設定
# GOOGLE_API_KEY または OPENAI_API_KEY を設定
```

### 3. アプリケーションの起動

```bash
# サービスをビルド・起動
docker compose up -d

# 初回起動の確認（ヘルスチェック）
docker compose ps
```

### 4. アクセス

- **アプリケーション**: http://localhost:3000
- **API ドキュメント**: http://localhost:8000/docs
- **NetworkXMCP**: http://localhost:8001/docs

## 🔐 認証システム

### ユーザー登録・ログイン

```bash
# 1. ユーザー登録
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'

# 2. トークン取得
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"
```

### 保護されたAPIの使用

```bash
# 3. LLM機能の使用（認証必須）
curl -X POST "http://localhost:8000/chatgpt/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "ネットワーク可視化について教えて"}'
```

## 🤖 AI機能

### レイアウト推薦システム

ネットワークの特性を分析し、最適なレイアウトアルゴリズムを提案：

```bash
curl -X POST "http://localhost:8000/chatgpt/recommend-layout" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "ソーシャルネットワーク、500ノード、2000エッジ",
    "purpose": "コミュニティ構造の可視化"
  }'
```

### サポートされているLLMプロバイダー

- **Google Gemini**: 高速で効率的な応答
- **OpenAI**: GPT-4oモデルによる高精度な分析

設定方法は [docs/LLM_PROVIDER_GUIDE.md](docs/LLM_PROVIDER_GUIDE.md) を参照してください。

## 📊 ネットワーク分析機能

### サポートされているレイアウトアルゴリズム

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

### ネットワーク形式

- **GraphML**: 標準的なグラフ交換形式
- **GML**: Graph Modeling Language
- **JSON**: カスタムネットワーク形式

## 🔧 開発環境

### ローカル開発セットアップ

```bash
# APIサーバー（ターミナル1）
cd API
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn main:app --reload

# NetworkXMCPサーバー（ターミナル2）
cd NetworkXMCP
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn main:app --port 8001 --reload

# フロントエンド（ターミナル3）
cd frontend
npm install
npm run dev
```

詳細は [AGENTS.md](AGENTS.md) を参照してください。

## 📝 ドキュメント

- [📖 クイックスタートガイド](docs/QUICK_START.md)
- [🤖 LLMプロバイダー設定](docs/LLM_PROVIDER_GUIDE.md)
- [🧪 テスト実行ガイド](docs/TESTING_GUIDE.md)
- [🛠️ AI Agents開発ガイド](AGENTS.md)
- [⚙️ NetworkXMCP詳細](NetworkXMCP/README.md)
- [📊 ネットワークレイアウト機能](docs/README_network_layout.md)

## 🧪 テスト

```bash
# すべてのテストを実行
./run_tests.sh

# 特定のサービスのテスト
./run_tests.sh --skip-integration
docker compose -f docker-compose.test.yml up api-test
```

## 📋 APIエンドポイント

### 認証

- `POST /auth/register` - ユーザー登録
- `POST /auth/token` - アクセストークン取得
- `GET /auth/users/me` - ユーザー情報取得

### LLM統合

- `POST /chatgpt/generate` - AI応答生成
- `POST /chatgpt/recommend-layout` - レイアウト推薦

### ネットワーク分析

- `POST /network/layout` - レイアウト計算
- `POST /network/upload` - ネットワークファイルアップロード
- `GET /network/formats` - サポート形式一覧

## 🤝 コントリビューション

1. フォークを作成
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチをプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

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
