# ネットワークレイアウトAPI

このAPIは、ネットワークデータとレイアウトアルゴリズムのパラメーターを受け取り、選択されたレイアウトアルゴリズムを適用して、更新されたノード位置を含むネットワークデータを返します。

## エンドポイント

```
POST /network-layout/apply
```

## リクエスト形式

```json
{
  "nodes": [
    {
      "id": "string",
      "label": "string" (オプション)
    }
  ],
  "edges": [
    {
      "source": "string",
      "target": "string"
    }
  ],
  "layout": "string",
  "layout_params": {
    // レイアウトアルゴリズム固有のパラメータ
  }
}
```

### パラメーター

- `nodes`: ネットワークのノードリスト
  - `id`: ノードの一意の識別子
  - `label`: ノードのラベル（オプション）
- `edges`: ネットワークのエッジリスト
  - `source`: エッジの始点ノードID
  - `target`: エッジの終点ノードID
- `layout`: 使用するレイアウトアルゴリズム
- `layout_params`: レイアウトアルゴリズムに渡すパラメーター（オプション）

## レスポンス形式

```json
{
  "nodes": [
    {
      "id": "string",
      "x": float,
      "y": float,
      "label": "string" (オプション)
    }
  ],
  "edges": [
    {
      "source": "string",
      "target": "string"
    }
  ]
}
```

### レスポンスフィールド

- `nodes`: 位置情報が追加されたノードリスト
  - `id`: ノードの一意の識別子
  - `x`: X座標
  - `y`: Y座標
  - `label`: ノードのラベル（オプション）
- `edges`: 元のエッジリスト

## サポートされているレイアウトアルゴリズム

以下のレイアウトアルゴリズムがサポートされています：

1. `spring` - バネと電気モデルを使用したフォースダイレクテッドレイアウト
2. `circular` - ノードを円上に配置
3. `random` - ランダムなノード位置
4. `spectral` - グラフラプラシアンの固有ベクトルを使用
5. `shell` - ノードを同心円上に配置
6. `spiral` - ノードをスパイラル状に配置
7. `kamada_kawai` - エネルギー最小化に基づくフォースダイレクテッドレイアウト
8. `fruchterman_reingold` - フォースダイレクテッドレイアウトアルゴリズム
9. `bipartite` - 二部グラフ用レイアウト
10. `multipartite` - 多部グラフ用レイアウト
11. `planar` - 平面グラフ用レイアウト（グラフが平面の場合のみ）

## レイアウトパラメーターの例

各レイアウトアルゴリズムは特定のパラメーターを受け入れることができます。以下に一般的なパラメーターの例を示します：

### springレイアウト

```json
{
  "k": 0.1,       // バネ定数
  "iterations": 50 // 反復回数
}
```

### fruchterman_reingoldレイアウト

```json
{
  "k": 0.5,        // 最適距離定数
  "iterations": 50, // 反復回数
  "weight": "weight" // エッジの重みに使用する属性名
}
```

### circularレイアウト

```json
{
  "scale": 1.0,    // スケール係数
  "center": [0, 0] // 中心座標
}
```

## 使用例

### リクエスト例

```json
{
  "nodes": [
    {"id": "1", "label": "Node 1"},
    {"id": "2", "label": "Node 2"},
    {"id": "3", "label": "Node 3"},
    {"id": "4", "label": "Node 4"},
    {"id": "5", "label": "Node 5"}
  ],
  "edges": [
    {"source": "1", "target": "2"},
    {"source": "1", "target": "3"},
    {"source": "2", "target": "3"},
    {"source": "3", "target": "4"},
    {"source": "4", "target": "5"},
    {"source": "5", "target": "1"}
  ],
  "layout": "circular",
  "layout_params": {
    "scale": 1.5,
    "center": [0, 0]
  }
}
```

### レスポンス例

```json
{
  "nodes": [
    {"id": "1", "x": 1.5, "y": 0.0, "label": "Node 1"},
    {"id": "2", "x": 0.4635254915624211, "y": 1.4265847744427305, "label": "Node 2"},
    {"id": "3", "x": -1.2135254915624213, "y": 0.8816778784387097, "label": "Node 3"},
    {"id": "4", "x": -1.2135254915624213, "y": -0.8816778784387097, "label": "Node 4"},
    {"id": "5", "x": 0.4635254915624211, "y": -1.4265847744427305, "label": "Node 5"}
  ],
  "edges": [
    {"source": "1", "target": "2"},
    {"source": "1", "target": "3"},
    {"source": "2", "target": "3"},
    {"source": "3", "target": "4"},
    {"source": "4", "target": "5"},
    {"source": "5", "target": "1"}
  ]
}
```

## フロントエンドでの使用方法

フロントエンドでは、`networkStore.js`の`applyLayout`メソッドを使用してこのAPIを呼び出すことができます：

```javascript
// レイアウトを適用する
const applyLayout = async () => {
  const { nodes, edges, layout, layoutParams } = get();
  
  if (!nodes.length) {
    set({ error: 'No nodes provided' });
    return false;
  }

  set({ isLoading: true, error: null });
  try {
    const response = await networkAPI.applyLayout(
      nodes, 
      edges, 
      layout, 
      layoutParams
    );
    
    set({ 
      positions: response.data.nodes,
      isLoading: false,
      error: null
    });
    
    return true;
  } catch (error) {
    set({ 
      isLoading: false, 
      error: error.response?.data?.detail || 'Layout application failed'
    });
    return false;
  }
};
```

## エラーレスポンス

エラーが発生した場合、APIは適切なHTTPステータスコードとエラーメッセージを返します：

```json
{
  "detail": "エラーメッセージ"
}
```

一般的なエラーコード：
- `400 Bad Request`: 無効なリクエストパラメーター
- `401 Unauthorized`: 認証エラー
- `500 Internal Server Error`: サーバー内部エラー
