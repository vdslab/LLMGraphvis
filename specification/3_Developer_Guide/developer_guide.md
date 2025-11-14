# LLMGraphvis 開発者ガイド

## 概要

このガイドは、LLMGraphvisプロジェクトの開発者向けに、開発環境のセットアップ、コーディング規約、テスト方法、デプロイ方法などを説明します。

## 目次

1. [プロジェクト構造](#プロジェクト構造)
2. [開発環境のセットアップ](#開発環境のセットアップ)
3. [コーディング規約](#コーディング規約)
4. [テスト方法](#テスト方法)
5. [デプロイ方法](#デプロイ方法)
6. [トラブルシューティング](#トラブルシューティング)
7. [よくある質問](#よくある質問)

## プロジェクト構造

LLMGraphvisプロジェクトは、以下の主要なコンポーネントで構成されています。

```
LLMGraphvis/
  ├── API/                # バックエンドAPI
  │   ├── models/         # データベースモデル
  │   ├── schemas/        # APIスキーマ
  │   ├── routers/        # APIルーター
  │   ├── services/       # サービス
  │   └── core/           # コア機能
  │
  ├── NetworkXAPI/        # ネットワーク分析サービス
  │   ├── api/            # APIエンドポイント
  │   ├── database/       # データベース関連
  │   ├── graphml/        # GraphML処理
  │   ├── tools/          # ネットワーク処理ツール
  │   ├── layouts/        # レイアウトアルゴリズム
  │   ├── metrics/        # 中心性指標計算
  │   ├── cache/          # キャッシュ管理
  │   └── core/           # コア機能
  │
  ├── common/             # 共通モジュール
  │   ├── models/         # 共通モデル
  │   ├── utils/          # 共通ユーティリティ
  │   ├── exceptions/     # 共通例外
  │   └── logging/        # 共通ロギング
  │
  ├── frontend/           # フロントエンド
  │   ├── public/         # 静的ファイル
  │   └── src/            # ソースコード
  │
  ├── specification/      # 仕様書
  └── Sample/             # サンプルデータ
```

### 主要なモジュールの責務

#### API

- **models/**: データベースモデルの定義
- **schemas/**: APIリクエスト/レスポンススキーマの定義
- **routers/**: APIエンドポイントの定義
- **services/**: ビジネスロジックの実装
- **core/**: コア機能（認証、エラーハンドリングなど）

#### NetworkXAPI

- **api/**: APIエンドポイントの定義
- **database/**: データベース関連の処理
- **graphml/**: GraphML処理の実装
- **tools/**: ネットワーク処理ツールの実装
- **layouts/**: レイアウトアルゴリズムの実装
- **metrics/**: 中心性指標計算の実装
- **cache/**: キャッシュ管理の実装
- **core/**: コア機能（エラーハンドリングなど）

#### common

- **models/**: 共通モデルの定義
- **utils/**: 共通ユーティリティの実装
- **exceptions/**: 共通例外の定義
- **logging/**: 共通ロギングの実装

## 開発環境のセットアップ

### 前提条件

- Python 3.9以上
- Node.js 16以上
- Docker
- Docker Compose

### ローカル開発環境のセットアップ

1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/LLMGraphvis.git
cd LLMGraphvis
```

2. 環境変数の設定

```bash
cp .env.example .env
```

`.env`ファイルを編集して、必要な環境変数を設定します。

3. バックエンドのセットアップ

```bash
# APIのセットアップ
cd API
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate
pip install -e .

# NetworkXAPIのセットアップ
cd ../NetworkXAPI
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate
pip install -e .
```

4. フロントエンドのセットアップ

```bash
cd ../frontend
npm install
```

5. データベースのセットアップ

```bash
cd ..
./run_postgres_local.sh
```

6. サービスの起動

```bash
# APIの起動
cd API
uvicorn main:app --reload --port 8000

# NetworkXAPIの起動
cd ../NetworkXAPI
uvicorn main:app --reload --port 8001

# フロントエンドの起動
cd ../frontend
npm run dev
```

### Docker環境のセットアップ

1. Dockerイメージのビルド

```bash
docker-compose build
```

2. サービスの起動

```bash
docker-compose up
```

## コーディング規約

### Python

- [PEP 8](https://www.python.org/dev/peps/pep-0008/)に準拠したコードを書く
- [Black](https://github.com/psf/black)を使用してコードをフォーマットする
- [isort](https://github.com/PyCQA/isort)を使用してインポートを整理する
- [Flake8](https://flake8.pycqa.org/en/latest/)を使用してコードをリントする
- [mypy](https://mypy.readthedocs.io/en/stable/)を使用して型チェックを行う

#### 命名規則

- **クラス名**: `CamelCase`
- **関数名**: `snake_case`
- **変数名**: `snake_case`
- **定数名**: `UPPER_CASE`
- **モジュール名**: `snake_case`
- **パッケージ名**: `snake_case`

#### ドキュメンテーション

- すべての関数、クラス、メソッドにはDocstringを記述する
- Docstringは[Google Style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)に準拠する

```python
def calculate_centrality(G, centrality_type="degree", **kwargs):
    """
    中心性指標を計算します。
    
    Args:
        G: NetworkXグラフ
        centrality_type: 中心性タイプ
        **kwargs: 追加のパラメータ
        
    Returns:
        ノードIDをキー、中心性値を値とする辞書
        
    Raises:
        ValueError: 無効な中心性タイプが指定された場合
    """
    # 実装
```

### JavaScript/TypeScript

- [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)に準拠したコードを書く
- [ESLint](https://eslint.org/)を使用してコードをリントする
- [Prettier](https://prettier.io/)を使用してコードをフォーマットする

#### 命名規則

- **コンポーネント名**: `PascalCase`
- **関数名**: `camelCase`
- **変数名**: `camelCase`
- **定数名**: `UPPER_CASE`
- **ファイル名**: コンポーネントは`PascalCase`、それ以外は`camelCase`

#### ドキュメンテーション

- すべての関数、コンポーネント、クラスにはJSDocを記述する

```javascript
/**
 * ネットワークデータを可視化します。
 * 
 * @param {Object} data - ネットワークデータ
 * @param {Array} data.nodes - ノードのリスト
 * @param {Array} data.links - リンクのリスト
 * @param {Object} options - 可視化オプション
 * @returns {Object} 可視化結果
 */
function visualizeNetwork(data, options) {
    // 実装
}
```

## テスト方法

### バックエンドのテスト

#### ユニットテスト

```bash
# APIのユニットテスト
cd API
pytest tests/unit

# NetworkXAPIのユニットテスト
cd ../NetworkXAPI
pytest tests/unit
```

#### 統合テスト

```bash
# APIの統合テスト
cd API
pytest tests/integration

# NetworkXAPIの統合テスト
cd ../NetworkXAPI
pytest tests/integration
```

#### システムテスト

```bash
# システムテスト
cd ..
pytest test_system_integration.py
```

### フロントエンドのテスト

```bash
cd frontend
npm test
```

### テストカバレッジの確認

```bash
# APIのテストカバレッジ
cd API
pytest --cov=.

# NetworkXAPIのテストカバレッジ
cd ../NetworkXAPI
pytest --cov=.

# フロントエンドのテストカバレッジ
cd ../frontend
npm test -- --coverage
```

## デプロイ方法

### 本番環境へのデプロイ

1. 本番用の環境変数を設定

```bash
cp .env.example .env.prod
```

`.env.prod`ファイルを編集して、本番環境用の環境変数を設定します。

2. 本番用のDockerイメージをビルド

```bash
docker-compose -f docker-compose.prod.yml build
```

3. 本番環境にデプロイ

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### CI/CDパイプライン

LLMGraphvisプロジェクトでは、GitHub Actionsを使用してCI/CDパイプラインを構築しています。

#### CI（継続的インテグレーション）

- プルリクエストが作成されると、自動的にテストが実行されます
- コードスタイルのチェックが行われます
- テストカバレッジが計算されます

#### CD（継続的デリバリー）

- mainブランチにマージされると、自動的にステージング環境にデプロイされます
- リリースタグが作成されると、自動的に本番環境にデプロイされます

## トラブルシューティング

### よくあるエラーと解決策

#### データベース接続エラー

**エラー**:
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server: Connection refused
```

**解決策**:
1. PostgreSQLサービスが起動しているか確認する
2. `.env`ファイルのデータベース接続情報が正しいか確認する
3. ネットワーク設定を確認する

#### NetworkXAPI通信エラー

**エラー**:
```
APICommunicationError: Error from NetworkXAPI: Connection refused
```

**解決策**:
1. NetworkXAPIサービスが起動しているか確認する
2. `.env`ファイルの`NETWORKX_API_URL`が正しいか確認する
3. ネットワーク設定を確認する

#### GraphML検証エラー

**エラー**:
```
GraphMLValidationError: Invalid GraphML content: Missing <graph> element
```

**解決策**:
1. GraphMLファイルの内容を確認する
2. GraphMLファイルが正しい形式か確認する
3. 必要に応じて、GraphMLファイルを修正する

## よくある質問

### Q: 新しいレイアウトアルゴリズムを追加するにはどうすればよいですか？

A: 以下の手順で新しいレイアウトアルゴリズムを追加できます。

1. `NetworkXAPI/layouts/layout_functions.py`に新しいレイアウト関数を追加する
2. `get_layout_function`関数に新しいレイアウトを登録する
3. 必要に応じて、テストを追加する

### Q: 新しい中心性指標を追加するにはどうすればよいですか？

A: 以下の手順で新しい中心性指標を追加できます。

1. `NetworkXAPI/metrics/centrality_functions.py`に新しい中心性関数を追加する
2. `get_centrality_function`関数に新しい中心性を登録する
3. 必要に応じて、テストを追加する

### Q: 大規模グラフの処理でパフォーマンスの問題が発生した場合、どうすればよいですか？

A: 以下の対策を検討してください。

1. キャッシュを活用する
2. 非同期処理を使用する
3. 部分計算を行う
4. 近似アルゴリズムを使用する
5. サーバーのリソースを増やす

### Q: 新しいAPIエンドポイントを追加するにはどうすればよいですか？

A: 以下の手順で新しいAPIエンドポイントを追加できます。

1. 必要に応じて、`API/models/`に新しいモデルを追加する
2. 必要に応じて、`API/schemas/`に新しいスキーマを追加する
3. `API/routers/`に新しいルーターを追加する
4. 必要に応じて、`API/services/`に新しいサービスを追加する
5. `API/main.py`で新しいルーターを登録する
6. テストを追加する

### Q: フロントエンドに新しい機能を追加するにはどうすればよいですか？

A: 以下の手順で新しい機能を追加できます。

1. 必要に応じて、`frontend/src/services/`に新しいサービスを追加する
2. 必要に応じて、`frontend/src/components/`に新しいコンポーネントを追加する
3. 必要に応じて、`frontend/src/pages/`に新しいページを追加する
4. 必要に応じて、`frontend/src/App.jsx`でルーティングを更新する
5. テストを追加する

## 貢献ガイドライン

### プルリクエストのプロセス

1. 新しい機能やバグ修正のためのブランチを作成する
2. コードを変更する
3. テストを追加または更新する
4. コードスタイルを確認する
5. プルリクエストを作成する
6. コードレビューを受ける
7. 必要に応じて、コードを修正する
8. プルリクエストがマージされる

### コミットメッセージの規約

コミットメッセージは、以下の形式に従ってください。

```
<type>(<scope>): <subject>

<body>

<footer>
```

- **type**: コミットの種類（feat, fix, docs, style, refactor, test, chore）
- **scope**: コミットの影響範囲（api, networkx_api, frontend, common）
- **subject**: コミットの簡潔な説明
- **body**: コミットの詳細な説明
- **footer**: 関連するIssueやBreaking Changesの情報

例:
```
feat(api): ネットワークエクスポート機能の追加

- GraphMLエクスポート機能を追加
- エクスポート時のエラーハンドリングを改善

Closes #123
```

## 参考リンク

- [FastAPI公式ドキュメント](https://fastapi.tiangolo.com/)
- [NetworkX公式ドキュメント](https://networkx.org/)
- [React公式ドキュメント](https://reactjs.org/)
- [Docker公式ドキュメント](https://docs.docker.com/)
- [PostgreSQL公式ドキュメント](https://www.postgresql.org/docs/)