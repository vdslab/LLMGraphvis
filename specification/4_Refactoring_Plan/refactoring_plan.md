# LLMGraphvis リファクタリング計画

## 概要

このドキュメントは、LLMGraphvisプロジェクトのリファクタリング計画を詳細に記述したものです。リファクタリングの目的は、コードベースをより保守しやすく、拡張しやすくするとともに、LLMによる理解と開発を容易にすることです。

## 1. 共通モジュールの整理と抽出

### 1.1 API/NetworkXMCP間で共通のデータモデル定義を抽出

**現状の課題:**
- API側とNetworkXMCP側で重複するデータモデル定義が存在する
- 特にNetworkとConversationモデルが両方のサービスで定義されている
- モデル間の整合性を維持するのが困難

**改善計画:**
1. 共通のデータモデル定義を `common/models/` ディレクトリに移動
2. 以下のモデルを共通化:
   - `Network`: ネットワークデータモデル
   - `Conversation`: 会話データモデル
   - `GraphMLData`: GraphML形式のデータを表現するモデル
3. SQLAlchemyモデルとPydanticスキーマを分離
4. 共通モデルをAPI側とNetworkXMCP側の両方から参照できるようにする

**ディレクトリ構造:**
```
common/
  models/
    __init__.py
    base.py        # 基本モデル定義
    network.py     # ネットワーク関連モデル
    conversation.py # 会話関連モデル
    graphml.py     # GraphML関連モデル
```

### 1.2 GraphML処理ユーティリティの共通化

**現状の課題:**
- GraphML処理コードがAPI側とNetworkXMCP側で重複している
- 特に変換・パース処理に重複がある
- 機能拡張時に両方のコードを更新する必要がある

**改善計画:**
1. GraphML処理ユーティリティを `common/utils/graphml/` ディレクトリに移動
2. 以下の機能を共通化:
   - GraphMLパース処理
   - GraphML変換処理
   - GraphML検証処理
   - GraphML修正処理
3. NetworkXの依存関係を明確に分離し、必要な場合のみ使用

**ディレクトリ構造:**
```
common/
  utils/
    graphml/
      __init__.py
      parser.py     # パース機能
      converter.py  # 変換機能
      validator.py  # 検証機能
      fixer.py      # 修正機能
```

### 1.3 共通例外クラスの定義

**現状の課題:**
- 例外処理が統一されていない
- API側とNetworkXMCP側で異なる例外クラスを使用
- エラーメッセージの形式が不統一

**改善計画:**
1. 共通の例外クラス階層を `common/exceptions/` ディレクトリに定義
2. 以下の例外クラスを作成:
   - `BaseError`: すべての例外の基底クラス
   - `GraphMLError`: GraphML処理関連の例外
   - `NetworkError`: ネットワーク処理関連の例外
   - `MCPError`: MCP通信関連の例外
3. 例外クラスにエラーコード、メッセージ、コンテキスト情報を含める

**ディレクトリ構造:**
```
common/
  exceptions/
    __init__.py
    base.py       # 基本例外クラス
    graphml.py    # GraphML関連例外
    network.py    # ネットワーク関連例外
    mcp.py        # MCP関連例外
```

### 1.4 共通ロギング設定の統一

**現状の課題:**
- ロギング設定が各モジュールで個別に行われている
- ログフォーマットが不統一
- ログレベルの管理が困難

**改善計画:**
1. 共通のロギング設定を `common/logging/` ディレクトリに定義
2. 以下の機能を提供:
   - 統一されたログフォーマット
   - 環境変数によるログレベル制御
   - 構造化ロギングのサポート
3. すべてのモジュールで共通のロギング設定を使用

**ディレクトリ構造:**
```
common/
  logging/
    __init__.py
    config.py     # ロギング設定
    formatters.py # ログフォーマッター
```

## 2. API側のネットワーク機能モジュール分割

### 2.1 network.pyをサブモジュールに分割

**現状の課題:**
- `API/routers/network.py` が390行と大きすぎる
- 複数の責務が混在している
- 機能追加時に複雑性が増す

**改善計画:**
1. `API/routers/network/` ディレクトリを作成
2. 以下のサブモジュールに分割:
   - `__init__.py`: ルーターの初期化と集約
   - `upload.py`: ネットワークアップロード機能
   - `export.py`: ネットワークエクスポート機能
   - `visualization.py`: ビジュアライゼーション機能
   - `layout.py`: レイアウト処理機能

**ディレクトリ構造:**
```
API/
  routers/
    network/
      __init__.py
      upload.py
      export.py
      visualization.py
      layout.py
```

### 2.2 GraphML処理機能の分離

**現状の課題:**
- GraphML処理コードがルーター内に直接記述されている
- 再利用性が低い
- テストが困難

**改善計画:**
1. GraphML処理機能を `API/services/graphml/` ディレクトリに移動
2. 以下の機能を提供:
   - GraphMLファイルの検証
   - GraphMLファイルの変換
   - GraphMLファイルのパース
3. 共通モジュールの `common/utils/graphml/` を活用

**ディレクトリ構造:**
```
API/
  services/
    graphml/
      __init__.py
      validator.py
      converter.py
      parser.py
```

### 2.3 ビジュアライゼーション機能の分離

**現状の課題:**
- ビジュアライゼーション関連のコードがルーター内に直接記述されている
- 視覚化形式の追加が困難
- コードの重複が発生しやすい

**改善計画:**
1. ビジュアライゼーション機能を `API/services/visualization/` ディレクトリに移動
2. 以下の機能を提供:
   - Cytoscape.js形式への変換
   - 汎用ビジュアライゼーションデータ形式への変換
   - カスタム視覚化形式のサポート

**ディレクトリ構造:**
```
API/
  services/
    visualization/
      __init__.py
      cytoscape.py
      visdata.py
      custom.py
```

### 2.4 レイアウト処理機能の分離

**現状の課題:**
- レイアウト処理がルーター内に直接記述されている
- MCP通信コードとビジネスロジックが混在している
- 新しいレイアウトアルゴリズムの追加が困難

**改善計画:**
1. レイアウト処理機能を `API/services/layout/` ディレクトリに移動
2. 以下の機能を提供:
   - レイアウトアルゴリズムの管理
   - レイアウトパラメータの検証
   - レイアウト結果の処理

**ディレクトリ構造:**
```
API/
  services/
    layout/
      __init__.py
      manager.py
      validator.py
      processor.py
```

## 3. NetworkXMCPのモジュール構造改善

### 3.1 main.pyからデータベース関連コードの分離

**現状の課題:**
- `NetworkXMCP/main.py` にデータベース関連コードが直接記述されている
- SQLAlchemyモデルとAPIエンドポイントが混在している
- コードの再利用性が低い

**改善計画:**
1. データベース関連コードを `NetworkXMCP/database/` ディレクトリに移動
2. 以下のモジュールを作成:
   - `__init__.py`: データベース初期化
   - `models.py`: SQLAlchemyモデル定義
   - `session.py`: セッション管理
   - `operations.py`: データベース操作

**ディレクトリ構造:**
```
NetworkXMCP/
  database/
    __init__.py
    models.py
    session.py
    operations.py
```

### 3.2 tools/network_tools.pyの機能別分割

**現状の課題:**
- `NetworkXMCP/tools/network_tools.py` が915行と非常に大きい
- 複数の責務が混在している
- 機能追加時に複雑性が増す

**改善計画:**
1. `NetworkXMCP/tools/` ディレクトリ内のファイルを機能別に分割
2. 以下のモジュールを作成:
   - `creation.py`: ネットワーク作成機能
   - `parsing.py`: ネットワークパース機能
   - `export.py`: ネットワークエクスポート機能
   - `analysis.py`: ネットワーク分析機能

**ディレクトリ構造:**
```
NetworkXMCP/
  tools/
    __init__.py
    creation.py
    parsing.py
    export.py
    analysis.py
```

### 3.3 GraphML変換処理の専用モジュール化

**現状の課題:**
- GraphML変換処理が `network_tools.py` 内に直接記述されている
- コードが複雑で理解しにくい
- 機能拡張が困難

**改善計画:**
1. GraphML変換処理を `NetworkXMCP/graphml/` ディレクトリに移動
2. 以下のモジュールを作成:
   - `__init__.py`: モジュール初期化
   - `converter.py`: GraphML変換機能
   - `validator.py`: GraphML検証機能
   - `fixer.py`: GraphML修正機能
3. 共通モジュールの `common/utils/graphml/` を活用

**ディレクトリ構造:**
```
NetworkXMCP/
  graphml/
    __init__.py
    converter.py
    validator.py
    fixer.py
```

### 3.4 キャッシュ管理機能の分離

**現状の課題:**
- キャッシュ管理コードがAPIエンドポイント内に直接記述されている
- キャッシュ戦略の変更が困難
- キャッシュの一貫性管理が複雑

**改善計画:**
1. キャッシュ管理機能を `NetworkXMCP/cache/` ディレクトリに移動
2. 以下のモジュールを作成:
   - `__init__.py`: モジュール初期化
   - `manager.py`: キャッシュ管理
   - `strategies.py`: キャッシュ戦略
   - `invalidation.py`: キャッシュ無効化

**ディレクトリ構造:**
```
NetworkXMCP/
  cache/
    __init__.py
    manager.py
    strategies.py
    invalidation.py
```

## 4. データモデルとスキーマの整理

### 4.1 API/models.pyの機能別分割

**現状の課題:**
- `API/models.py` に複数のデータモデルが混在している
- モデル間の関係が複雑
- 機能追加時に複雑性が増す

**改善計画:**
1. `API/models/` ディレクトリを作成
2. 以下のモジュールに分割:
   - `__init__.py`: モデルのエクスポート
   - `user.py`: ユーザー関連モデル
   - `conversation.py`: 会話関連モデル
   - `network.py`: ネットワーク関連モデル
   - `chat.py`: チャット関連モデル

**ディレクトリ構造:**
```
API/
  models/
    __init__.py
    user.py
    conversation.py
    network.py
    chat.py
```

### 4.2 API/schemas.pyの機能別分割

**現状の課題:**
- `API/schemas.py` に複数のスキーマが混在している
- スキーマ間の関係が複雑
- 機能追加時に複雑性が増す

**改善計画:**
1. `API/schemas/` ディレクトリを作成
2. 以下のモジュールに分割:
   - `__init__.py`: スキーマのエクスポート
   - `user.py`: ユーザー関連スキーマ
   - `conversation.py`: 会話関連スキーマ
   - `network.py`: ネットワーク関連スキーマ
   - `chat.py`: チャット関連スキーマ

**ディレクトリ構造:**
```
API/
  schemas/
    __init__.py
    user.py
    conversation.py
    network.py
    chat.py
```

### 4.3 NetworkXMCPのモデル定義の整理

**現状の課題:**
- NetworkXMCP側のモデル定義が `main.py` 内に直接記述されている
- Pydanticモデルとデータベースモデルが混在している
- モデル間の関係が不明確

**改善計画:**
1. `NetworkXMCP/models/` ディレクトリを作成
2. 以下のモジュールに分割:
   - `__init__.py`: モデルのエクスポート
   - `database.py`: データベースモデル
   - `api.py`: APIリクエスト/レスポンスモデル
   - `graph.py`: グラフデータモデル

**ディレクトリ構造:**
```
NetworkXMCP/
  models/
    __init__.py
    database.py
    api.py
    graph.py
```

### 4.4 共通モデル定義の作成

**現状の課題:**
- API側とNetworkXMCP側で重複するモデル定義がある
- モデル間の整合性を維持するのが困難
- 変更時に複数の場所を更新する必要がある

**改善計画:**
1. `common/models/` ディレクトリに共通モデル定義を作成
2. 以下のモジュールを作成:
   - `__init__.py`: モデルのエクスポート
   - `network.py`: ネットワーク共通モデル
   - `graph.py`: グラフデータ共通モデル
   - `response.py`: レスポンス共通モデル

**ディレクトリ構造:**
```
common/
  models/
    __init__.py
    network.py
    graph.py
    response.py
```

## 5. エラーハンドリングの統一

### 5.1 共通例外クラス階層の設計

**現状の課題:**
- 例外クラスが統一されていない
- エラーメッセージの形式が不統一
- エラーコンテキスト情報が不足している

**改善計画:**
1. `common/exceptions/` ディレクトリに共通例外クラス階層を設計
2. 以下の基本例外クラスを作成:
   - `BaseError`: すべての例外の基底クラス
   - `ValidationError`: 検証エラー
   - `ProcessingError`: 処理エラー
   - `CommunicationError`: 通信エラー
3. 各例外クラスにエラーコード、メッセージ、コンテキスト情報を含める

**ディレクトリ構造:**
```
common/
  exceptions/
    __init__.py
    base.py
    validation.py
    processing.py
    communication.py
```

### 5.2 API側のエラーハンドリング統一

**現状の課題:**
- API側のエラーハンドリングが統一されていない
- HTTPExceptionの使用方法が不統一
- エラーレスポンスの形式が不統一

**改善計画:**
1. `API/core/errors.py` にエラーハンドリング機能を集約
2. 以下の機能を提供:
   - 例外からHTTPExceptionへの変換
   - 統一されたエラーレスポンス形式
   - エラーログ記録
3. FastAPIのエラーハンドラーを使用して例外を捕捉

**実装例:**
```python
# API/core/errors.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from common.exceptions import BaseError

async def error_handler(request: Request, exc: BaseError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "context": exc.context
        }
    )

# API/main.py
from fastapi import FastAPI
from core.errors import error_handler
from common.exceptions import BaseError

app = FastAPI()
app.add_exception_handler(BaseError, error_handler)
```

### 5.3 NetworkXMCP側のエラーハンドリング統一

**現状の課題:**
- NetworkXMCP側のエラーハンドリングが統一されていない
- try-except文が多用されている
- エラーレスポンスの形式が不統一

**改善計画:**
1. `NetworkXMCP/core/errors.py` にエラーハンドリング機能を集約
2. 以下の機能を提供:
   - 例外からHTTPExceptionへの変換
   - 統一されたエラーレスポンス形式
   - エラーログ記録
3. FastAPIのエラーハンドラーを使用して例外を捕捉

**実装例:**
```python
# NetworkXMCP/core/errors.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from common.exceptions import BaseError

async def error_handler(request: Request, exc: BaseError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "context": exc.context
        }
    )

# NetworkXMCP/main.py
from fastapi import FastAPI
from core.errors import error_handler
from common.exceptions import BaseError

app = FastAPI()
app.add_exception_handler(BaseError, error_handler)
```

### 5.4 エラーレスポンス形式の標準化

**現状の課題:**
- エラーレスポンスの形式が不統一
- エラー情報が不足している
- クライアント側での処理が困難

**改善計画:**
1. `common/models/errors.py` に標準エラーレスポンスモデルを定義
2. 以下の情報を含める:
   - エラーコード: 一意のエラー識別子
   - メッセージ: 人間可読なエラーメッセージ
   - コンテキスト: エラーに関連する追加情報
   - タイムスタンプ: エラー発生時刻
3. すべてのAPIエンドポイントで標準エラーレスポンスを使用

**実装例:**
```python
# common/models/errors.py
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    context: Dict[str, Any] = {}
    timestamp: datetime = datetime.now()
```

## 6. ドキュメント整備

### 6.1 モジュール構造図の作成

**現状の課題:**
- プロジェクト全体の構造を理解するのが困難
- モジュール間の関係が不明確
- 新規開発者のオンボーディングが困難

**改善計画:**
1. `specification/architecture/` ディレクトリにモジュール構造図を作成
2. 以下の図を含める:
   - プロジェクト全体の構造図
   - API側のモジュール構造図
   - NetworkXMCP側のモジュール構造図
   - 共通モジュールの構造図
3. PlantUML形式で作成し、ソースコードとともにバージョン管理

**ディレクトリ構造:**
```
specification/
  architecture/
    overview.puml
    api.puml
    networkx_mcp.puml
    common.puml
```

### 6.2 API仕様書の更新

**現状の課題:**
- API仕様書が不足している
- エンドポイントの詳細な説明が不足している
- リクエスト/レスポンスの例が不足している

**改善計画:**
1. `specification/api/` ディレクトリにAPI仕様書を作成
2. 以下の情報を含める:
   - エンドポイントの一覧
   - リクエスト/レスポンスの詳細
   - エラーレスポンスの詳細
   - 認証方法の説明
3. OpenAPI形式で作成し、FastAPIの自動ドキュメント生成と連携

**ディレクトリ構造:**
```
specification/
  api/
    openapi.yaml
    auth.md
    network.md
    chat.md
```

### 6.3 NetworkXMCP機能仕様書の作成

**現状の課題:**
- NetworkXMCP機能の仕様書が不足している
- 機能の詳細な説明が不足している
- 使用方法の説明が不足している

**改善計画:**
1. `specification/networkx_mcp/` ディレクトリに機能仕様書を作成
2. 以下の情報を含める:
   - 機能の一覧
   - 各機能の詳細な説明
   - パラメータの説明
   - 使用例
3. Markdown形式で作成し、GitHubでの閲覧を容易にする

**ディレクトリ構造:**
```
specification/
  networkx_mcp/
    overview.md
    layouts.md
    centrality.md
    graphml.md
```

### 6.4 開発者向けガイドの作成

**現状の課題:**
- 開発者向けガイドが不足している
- 開発環境のセットアップ手順が不足している
- コーディング規約が不足している

**改善計画:**
1. `specification/developer/` ディレクトリに開発者向けガイドを作成
2. 以下の情報を含める:
   - 開発環境のセットアップ手順
   - コーディング規約
   - テスト方法
   - デプロイ方法
3. Markdown形式で作成し、GitHubでの閲覧を容易にする

**ディレクトリ構造:**
```
specification/
  developer/
    setup.md
    coding_standards.md
    testing.md
    deployment.md
```

## 実装順序と依存関係

リファクタリングを効率的に進めるために、以下の順序で実装することを推奨します：

1. 共通モジュールの整理と抽出
   - 共通例外クラスの定義
   - 共通ロギング設定の統一
   - 共通モデル定義の作成
   - GraphML処理ユーティリティの共通化

2. エラーハンドリングの統一
   - 共通例外クラス階層の設計
   - エラーレスポンス形式の標準化
   - API側のエラーハンドリング統一
   - NetworkXMCP側のエラーハンドリング統一

3. データモデルとスキーマの整理
   - API/models.pyの機能別分割
   - API/schemas.pyの機能別分割
   - NetworkXMCPのモデル定義の整理

4. NetworkXMCPのモジュール構造改善
   - main.pyからデータベース関連コードの分離
   - tools/network_tools.pyの機能別分割
   - GraphML変換処理の専用モジュール化
   - キャッシュ管理機能の分離

5. API側のネットワーク機能モジュール分割
   - network.pyをサブモジュールに分割
   - GraphML処理機能の分離
   - ビジュアライゼーション機能の分離
   - レイアウト処理機能の分離

6. ドキュメント整備
   - モジュール構造図の作成
   - API仕様書の更新
   - NetworkXMCP機能仕様書の作成
   - 開発者向けガイドの作成

## 注意事項

- リファクタリング中はAPIの互換性を維持する
- 各ステップごとにテストを実行し、機能が正常に動作することを確認する
- 大きな変更は小さなステップに分割して実装する
- コードレビューを行い、品質を確保する