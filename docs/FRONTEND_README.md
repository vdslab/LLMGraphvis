# LLMGraphvis Frontend

LLMGraphvisプロジェクトのReact+Viteベースフロントエンドアプリケーション

## 技術スタック

- **React 18**: モダンなUIライブラリ
- **Vite**: 高速なビルドツールと開発サーバー
- **TypeScript**: 型安全な開発環境
- **Tailwind CSS**: ユーティリティファーストCSSフレームワーク
- **ESLint**: コード品質とスタイルの統一

## 特徴

- ⚡ **高速開発**: Viteによる即座のホットリロード（HMR）
- 🎨 **レスポンシブデザイン**: Tailwind CSSによるモダンなUI
- 🔐 **認証統合**: JWT認証によるセキュアなAPIアクセス
- 📊 **ネットワーク可視化**: インタラクティブなグラフ表示
- 🤖 **AI統合**: LLMによるレイアウト推薦機能

## 開発環境

### 前提条件

- Node.js v18以上
- npmまたはyarn

### セットアップ

```bash
# 依存関係のインストール
npm install

# 開発サーバーの起動
npm run dev

# ブラウザでアクセス
# http://localhost:3000
```

### 利用可能なスクリプト

```bash
# 開発サーバー起動
npm run dev

# プロダクションビルド
npm run build

# ビルド結果のプレビュー
npm run preview

# ESLintチェック
npm run lint

# ESLintエラー自動修正
npm run lint:fix
```

## 開発ガイド

### ESLint設定の拡張

プロダクションアプリケーションを開発する場合、TypeScriptと型を意識したリントルールの使用を推奨します。TypeScriptと[`typescript-eslint`](https://typescript-eslint.io)の統合については、[TSテンプレート](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts)を参照してください。

### 利用可能なプラグイン

現在、2つの公式プラグインが利用可能です：

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react): [Babel](https://babeljs.io/)を使用したFast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc): [SWC](https://swc.rs/)を使用したFast Refresh

## Docker環境

### 開発環境での実行

```bash
# Docker Composeを使用した起動
docker compose up frontend

# または、すべてのサービスと一緒に起動
docker compose up
```

### プロダクションビルド

```bash
# プロダクション用イメージのビルド
docker compose -f docker-compose.prod.yml build frontend

# プロダクション環境での実行
docker compose -f docker-compose.prod.yml up frontend
```

## API統合

フロントエンドは以下のAPIエンドポイントと統合されています：

- **認証API** (`http://localhost:8000/auth/*`)
- **ネットワーク分析API** (`http://localhost:8000/network/*`)
- **LLM統合API** (`http://localhost:8000/chatgpt/*`)

### 環境変数

```bash
# .env.local ファイルで設定
VITE_API_BASE_URL=http://localhost:8000
VITE_NETWORKX_MCP_URL=http://localhost:8001
```

## テスト

```bash
# テストの実行
npm test

# カバレッジ付きでテスト実行
npm run test:coverage

# テストのウォッチモード
npm run test:watch
```

## 関連ドキュメント

- [プロジェクトルートREADME](../README.md)
- [APIドキュメント](../API/)
- [NetworkXMCPドキュメント](../NetworkXMCP/README.md)
- [クイックスタートガイド](./QUICK_START.md)
