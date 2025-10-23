# グラフ計算サービス仕様 (NetworkXMCP)

## 1. 概要と役割

`NetworkXMCP` (NetworkX Model Context Protocol) は、グラフの計算処理に特化したステートレスなマイクロサービスです。

- **技術スタック**: FastAPI, NetworkX, Python
- **主な役割**:
    - `API`サービスからCPU負荷の高い計算処理をオフロードする。
    - `NetworkX`ライブラリを利用して、各種グラフ計算（レイアウト、指標分析）を実行する。
    - 様々な形式のGraphMLファイルを受け取り、システムで一貫して扱える標準形式に変換・正規化する。

## 2. APIエンドポイント一覧

`API`サービスから内部的に呼び出される、主要なツールエンドポイントです。

| Method | Path | 説明 |
|:---|:---|:---|
| `POST` | `/tools/change_layout` | 指定されたレイアウトアルゴリズムに基づき、グラフのノード座標を計算し、座標情報が追加されたGraphMLを返す。 |
| `POST` | `/tools/calculate_centrality` | 指定された中心性指標（次数、近接、媒介など）を計算し、各ノードの指標値を返す。 |
| `POST` | `/tools/convert_graphml` | アップロードされたGraphMLファイルを解析・修正し、標準的な属性（`name`, `color`, `size`など）と主要な中心性指標を持つ正規化されたGraphMLを返す。 |
| `POST` | `/tools/import_graphml` | GraphMLをパースし、ノードとエッジのリストをJSON形式で返す。 |
| `POST` | `/tools/export_graphml` | グラフデータをGraphML形式の文字列としてエクスポートする。 |
| `GET` | `/get_sample_network` | サンプルのランダムネットワークをGraphML形式で生成して返す。 |

## 3. 主要機能とデータフロー

### 3.1. GraphMLの正規化 (`/tools/convert_graphml`)

ユーザーがGraphMLファイルをアップロードした際の、最も重要な初期処理です。

1.  **入力**: `API`サービスが、ユーザーがアップロードしたGraphMLファイルの内容（文字列）をリクエストボディに含めて `POST /tools/convert_graphml` を呼び出す。
2.  **処理**:
    - 不完全なXML構造（ヘッダー、名前空間、閉じタグなど）を自動修正する。
    - `nx.read_graphml`でパースを試みる。
    - ノードの属性名（`label`, `node_color`など）を標準名（`name`, `color`）にマッピング・統一する。
    - `x`, `y`座標や`size`などの必須属性が存在しない場合は、デフォルト値やランダム値を補完する。
    - `degree_centrality`などの主要な中心性指標を事前に計算し、ノード属性として追加する。
3.  **出力**: 全てのノードとエッジが標準的な属性を持つ、正規化されたGraphML文字列を`API`サービスに返す。

### 3.2. レイアウト計算 (`/tools/change_layout`)

`Frontend`からの要求に応じて、グラフの見た目を動的に変更します。

1.  **入力**: `API`サービスが、現在のGraphMLデータ、レイアウト種別（`spring`, `circular`など）、およびパラメータ（`iterations`など）を `POST /tools/change_layout` に送信する。
2.  **処理**:
    - `NetworkX`の対応するレイアウト関数（`nx.spring_layout`など）を呼び出し、全ノードの新しい`(x, y)`座標を計算する。
    - 計算された座標をグラフのノード属性に上書きする。
3.  **出力**: レスポンスには2つの主要な情報が含まれる。
    - `positions`: 全ノードのIDと新しい座標のマップ。`Frontend`はこれを使って既存のグラフのノードを即座にアニメーションさせる。
    - `graphml_content`: 座標が更新された完全なGraphML文字列。`API`サービスはこれをデータベースに保存し、永続化する。

### 3.3. 中心性計算 (`/tools/calculate_centrality`)

LLMとの対話を通じて、特定のネットワーク指標を計算します。

1.  **入力**: `API`サービスが、現在のGraphMLデータと計算したい中心性の種類（`degree`, `betweenness`など）を `POST /tools/calculate_centrality` に送信する。
2.  **処理**: `NetworkX`の対応する関数（`nx.degree_centrality`など）を呼び出し、各ノードの中心性スコアを計算する。
3.  **出力**: 全ノードのIDと計算された中心性スコアのマップを返す。`API`サービスは、この数値データをLLMに渡し、「中心性が最も高いノードは…」といった自然言語の要約を生成させる。
