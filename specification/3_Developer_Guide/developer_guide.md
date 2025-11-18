# LLMGraphvis 開発者ガイド

## 1. はじめに

このガイドは、LLMGraphvisプロジェクトの開発に参加するための基本的な情報を提供します。本プロジェクトの目標は、大規模言語モデル（LLM）を活用して、直感的なネットワーク可視化と対話的な分析を実現する、軽量で効率的なプラットフォームを構築することです。

このドキュメントは、実装をゼロから再構築する現在の方針に基づき、意図的にシンプルに保たれています。

## 2. 技術スタックと前提条件

開発を始める前に、以下のツールがインストールされていることを確認してください。

- **Python**: 3.12 以上
- **Node.js**: 20.x 以上
- **Docker**: データベース（PostgreSQL）の起動にのみ使用します。

## 3. プロジェクト構造

プロジェクトは、明確な責務を持つ3つの主要なサービスで構成されます。

```
LLMGraphvis/
  ├── backend/          # バックエンド (FastAPI)
  ├── frontend/         # フロントエンド (React)
  └── networkx-api/     # ネットワーク計算サービス (FastAPI)
```

- **backend**: 認証、ビジネスロジック、LLMとの連携を担当します。
- **frontend**: ユーザーインターフェースを提供します。
- **networkx-api**: グラフ理論に基づいた計算（レイアウト、中心性など）を実行する専門サービスです。

## 4. ローカル開発環境のセットアップ

### Step 1: リポジトリのクローンと環境変数の設定

```bash
git clone https://github.com/your-repo/LLMGraphvis.git
cd LLMGraphvis

# 環境変数のテンプレートをコピー
cp .env.example .env
```
`.env`ファイルを開き、必要に応じて内容を編集してください。（通常はデフォルトのままで動作します）

### Step 2: データベースの起動

Dockerを使用してPostgreSQLデータベースを起動します。

```bash
docker-compose up -d postgres
```

### Step 3: 依存関係のインストール

各サービスのディレクトリに移動し、必要なパッケージをインストールします。

```bash
# バックエンド
cd backend
pip install -r requirements.txt

# ネットワーク計算サービス
cd ../networkx-api
pip install -r requirements.txt

# フロントエンド
cd ../frontend
npm install
```

### Step 4: サービスの起動

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

これで、`http://localhost:5173`（フロントエンドのデフォルトポート）にアクセスして開発を開始できます。

## 5. コーディング規約

コードの品質と一貫性を保つため、以下の規約に従ってください。

### Python (backend / networkx-api)

- **スタイルガイド**: [PEP 8](https://www.python.org/dev/peps/pep-0008/) に準拠します。コードの一貫性を保つため、以下のツールを使用します。
- **フォーマット**: [Black](https://github.com/psf/black) を使用して、PEP 8準拠のコードフォーマットを自動的に適用します。
- **インポート順序**: [isort](https://github.com/PyCQA/isort) を使用して、インポート文を整理します。
- **リント**: [Ruff](https://github.com/astral-sh/ruff) を使用して、スタイルガイド違反や潜在的なエラーを検出します。
- **型チェック**: [mypy](https://mypy.readthedocs.io/en/stable/) を使用します。
- **Docstring**: [Google Style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) に準拠します。

### JavaScript / TypeScript (frontend)

- **スタイルガイド**: [Google JavaScript Style Guide](https://google.github.io/styleguide/jsguide.html) に準拠します。
- **ツール**: [ESLint](https://eslint.org/) と [Prettier](https://prettier.io/) を使用し、`eslint-config-google` を設定して規約を強制します。
- **ドキュメンテーション**: すべての主要な関数とコンポーネントにはJSDocを記述します。

## 6. ブランチ戦略とコミットメッセージ

### ブランチ戦略

シンプルな **GitHub Flow** を採用します。

1.  `main` ブランチから、機能や修正内容を表す名前のブランチを作成します。（例: `feat/add-new-layout`, `fix/login-bug`）
2.  作業が完了したら、`main` ブランチに対するプルリクエストを作成します。
3.  コードレビューを経て、`main` ブランチにマージします。

### コミットメッセージ

コミットメッセージは [Conventional Commits](https://www.conventionalcommits.org/) の規約に従います。

- **書式**: `<type>(<scope>): <subject>`
- **type**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` のいずれか。
- **scope**: `backend`, `frontend`, `networkx-api` のいずれか。

**良い例:**
`feat(frontend): ユーザープロフィールのページを追加`

**悪い例:**
`バグ修正`

## 7. 参考リンク

- [FastAPI](https://fastapi.tiangolo.com/)
- [NetworkX](https://networkx.org/)
- [React](https://reactjs.org/)
- [Zustand](https://github.com/pmndrs/zustand)
- [Google JavaScript Style Guide](https://google.github.io/styleguide/jsguide.html)