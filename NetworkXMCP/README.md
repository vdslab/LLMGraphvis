# NetworkX MCP Server (FastMCP 2.0)

NetworkX Model Context Protocol (MCP) サーバーは、**FastMCP 2.0**を使用してネットワーク分析と可視化のためのAPIを提供します。OpenAPI仕様から自動的にMCPツールを生成し、GraphML形式のデータをサポートしてNetworkXを使用したグラフ分析を行います。

## 🚀 FastMCP 2.0への移行完了

このサーバーは`fastapi_mcp`から最新の**FastMCP 2.0**フレームワークへの移行が完了しています。

### 主な改善点

- ✅ **自動OpenAPI統合**: FastAPIのOpenAPI仕様からMCPツールを自動生成
- ✅ **10個のエンドポイント**: すべてのAPIエンドポイントがMCPツールとして利用可能
- ✅ **モダンアーキテクチャ**: 最新のMCPプロトコル標準を使用
- ✅ **高性能**: 向上した処理能力とサーバーレス対応
- ✅ **将来対応**: アクティブな開発とコミュニティサポート

詳細な移行情報については [../docs/FASTMCP_MIGRATION.md](../docs/FASTMCP_MIGRATION.md) をご覧ください。

## 機能

- GraphMLファイルのインポート/エクスポート
- ネットワークレイアウトの計算と適用
- 中心性指標の計算
- キャッシュ機能による高速処理
- 可視化データの生成
- FastMCP統合によるMCPツール自動生成

## 使用方法

### Docker Composeでの実行（推奨）

```bash
# サービスを開始
docker compose up networkx-mcp

# バックグラウンドで実行
docker compose up networkx-mcp -d

# ログを確認
docker compose logs networkx-mcp
```

### FastMCPサーバーの実行

```bash
# FastAPI ServerとFastMCPサーバーを個別に実行
docker compose exec networkx-mcp uv run python server_mcp.py
```

### 開発環境での実行

```bash
# 依存関係のインストール
uv sync

# サーバーの起動
uv run uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## APIエンドポイント（MCPツールとして利用可能）

### Resources (GET)

- `GET /health`: ヘルスチェック
- `GET /resources/graphs`: キャッシュされたグラフのリスト
- `GET /resources/graphs/{graph_id}`: キャッシュされたグラフの取得
- `GET /resources/cache/stats`: キャッシュ統計情報の取得

### Tools (POST)

- `POST /tools/create_network`: ネットワーク作成ツール
- `POST /tools/apply_layout`: レイアウト適用ツール
- `POST /tools/calculate_centrality`: 中心性計算ツール
- `POST /tools/create_visualization`: 可視化作成ツール

### Cache Management

- `DELETE /cache/clear`: キャッシュクリア

### 追加エンドポイント

- `GET /`: ルートエンドポイント

## OpenAPI仕様

FastMCP 2.0では、OpenAPI仕様が自動的にMCPツールに変換されます。

- **Swagger UI**: `http://localhost:8001/docs`
- **OpenAPI JSON**: `http://localhost:8001/openapi.json`
- **ReDoc**: `http://localhost:8001/redoc`

## アーキテクチャ

```
FastAPI App → OpenAPI Spec → FastMCP Server → MCP Tools
     ↓              ↓              ↓            ↓
HTTP Endpoints → JSON仕様 → MCPプロトコル → LLMアクセス
```

## 依存関係

### Core Dependencies

- **FastMCP**: `>=2.0.0` - Modern MCP server framework
- **FastAPI**: Web framework
- **NetworkX**: Graph analysis library
- **NumPy**: Numerical computing
- **httpx**: `>=0.27.0` - HTTP client for OpenAPI integration

### Development Dependencies

- **Uvicorn**: ASGI server
- **Pydantic**: Data validation

## 設定

### 環境変数

- `BASE_URL`: FastAPIサーバーのベースURL (デフォルト: `http://localhost:8001`)
- `LOG_LEVEL`: ログレベル (デフォルト: `INFO`)
- `FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER`: 実験的パーサーの有効化

### カスタム設定例

```python
from fastmcp.server.openapi import RouteMap, MCPType

# カスタムルートマッピング
route_maps = [
    RouteMap(methods=["GET"], mcp_type=MCPType.RESOURCE),
    RouteMap(methods=["POST"], mcp_type=MCPType.TOOL)
]

mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    route_maps=route_maps,
    tags={"networkx", "graph-analysis", "production"}
)
```

## テスト

```bash
# 健全性チェック
curl http://localhost:8001/health

# OpenAPI仕様の確認
curl http://localhost:8001/openapi.json | jq '.info'

# Swagger UIでのテスト
open http://localhost:8001/docs
```

## トラブルシューティング

### よくある問題

1. **AsyncIO競合**: MCPサーバー用の適切な非同期コンテキストを使用
2. **依存関係不足**: `httpx>=0.27.0`がインストールされていることを確認
3. **OpenAPIアクセス**: MCPサーバー前にFastAPIサーバーが実行されていることを確認

### デバッグコマンド

```bash
# コンテナーログの確認
docker compose logs networkx-mcp

# 依存関係の確認
docker compose exec networkx-mcp uv list

# OpenAPIエンドポイントのテスト
curl -s http://localhost:8001/openapi.json | jq '.info'
```

## ライセンス

MIT License
