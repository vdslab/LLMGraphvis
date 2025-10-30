## LLM Function Callingによるレンダリングデータ生成フロー

本ドキュメントは、ユーザーの自然言語指示に基づき、LLMの**Function Calling**機能を利用して動的にグラフのレンダリングデータを生成・更新する一連の処理フローを定義します。このフローは、[主要な処理フロー](./Interactions.md)のシーケンス図で示されるやり取りを、データの流れと責務の観点から詳細に記述したものです。

### 概要

ユーザーが「次数が多いノードを大きくして」のような曖昧な指示を出すと、システムは以下の手順でレンダリングデータを更新します。

1.  **Backend**がユーザーの指示を受け取り、LLMに送信します。
2.  **LLM**は、指示を解釈し、実行すべき**ツール（関数）**のリストをBackendに返します。
3.  **Backend**は、LLMの指示に従い、**NetworkXMCP**が提供するツールAPIを順次呼び出します。
4.  ツール実行後、**Backend**はデータベースから最新の状態を取得し、最終的なレンダリング用JSONを組み立てて**Frontend**に返します。

### データフローと責務

#### 1. Backend → LLM: ツール呼び出しの依頼

Backendは、LLMに対してユーザーの指示、会話履歴、そして利用可能なツール（関数）の定義を渡します。

- **入力 (コンテキスト情報)**:
    - **ユーザーのメッセージ**: `「友達が多い人を大きく表示して」`
    - **会話履歴**: 過去のやり取り。
    - **利用可能なツール定義**:
        - `calculate_centrality(type: str)`
        - `apply_metric_to_visual(metric: str, visual: str, mapping: dict)`
        - `change_layout(name: str)`
        - `highlight_nodes(metric: str, criteria: str)`
    - **現在のグラフ状態** (オプション): (これらはLLMへのプロンプトの一部、またはツール呼び出しのコンテキストとして渡されます)
        - `current_layout`: `spring`
        - `visual_mappings`: `{ "node_size": { "metric": "degree_centrality" } }`
    - **計算済みの指標リスト** (オプション): `['degree_centrality', 'pagerank']`
    - **グラフデータのスキーマ** (オプション): (LLMがツール引数を決定する際の判断材料となります)
        - `node_attributes`: `['name', 'department']`
        - `edge_attributes`: `['weight']`

#### 2. LLM → Backend: 実行すべきツールリストの返却

LLMは、ユーザーの指示を解釈し、どのツールをどの引数で呼び出すべきかを判断して、JSON形式で返します。一度に複数のツールコールを要求することもあります。

- **出力 (LLMからのツールコール要求)**:

```json
[
  {
    "tool_name": "calculate_centrality",
    "arguments": {
      "type": "degree" // この`type`は、`calculation_results`テーブルの`datatype`および`visual_styles`テーブルの`metric_type`と一貫している必要があります。
    }
  },
  {
    "tool_name": "apply_metric_to_visual",
    "arguments": {
      "metric": "degree_centrality",
      "visual": "node_size",
      "mapping": { "scale": "linear", "range": [8, 32] }
    }
  }
]
```

#### 3. Backend → NetworkXMCP: ツール実行

Backendは、LLMから受け取った指示に基づき、NetworkXMCPのAPIを呼び出します。このとき、NetworkXMCPは計算結果や可視化属性をデータベースに永続化します。

- `POST /tools/calculate_centrality` (引数: `{"type": "degree"}`)
- `POST /tools/apply_metric_to_visual` (引数: `{"metric": "degree_centrality", ...}`)

#### 4. Backend → Frontend: 最終レンダリングデータの返却

全てのツール実行が完了した後、Backendは**最終的な描画責任**を持ちます。データベースからノードの位置情報、ラベル、そしてツールによって更新された**スタイル情報**（サイズ、色など）をすべて取得し、Frontendがそのまま描画できる単一のJSONペイロードを組み立てて返します。

- **出力 (BackendからFrontendへのレスポンス)**:

```json
{
  "nodes": [
    {
      "id": "n1",
      "position": { "x": 120.5, "y": 300.2 },
      "label": "Zachary",
      "style": { // これらのスタイルプロパティは、`visual_styles`テーブルとその`mapping_config`から導出されます。
        "size": 32, // apply_metric_to_visualの結果が反映されている
        "color": "#4A90E2",
        "borderColor": "#0F172A",
        "borderWidth": 2
      }
    },
    {
      "id": "n2",
      "position": { "x": 240.0, "y": 180.7 },
      "label": "Node 2",
      "style": {
        "size": 14, // こちらも同様
        "color": "#F5A623",
        "borderColor": "#8A5A00",
        "borderWidth": 1
      }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "n1",
      "target": "n2",
      "label": "relates to",
      "style": { "color": "#888888", "width": 2 }
    }
  ]
}
```

### 設計上の要点

- **責務の分離**:
    - **LLM**: 自然言語を構造化されたツールコールに**変換**する。
    - **NetworkXMCP**: グラフに関する**計算と属性更新**に特化する。
    - **Backend**: LLMとツールの**オーケストレーション**と、最終的な**レンダリングデータの組み立て**を行う。
- **データの最小性**: Frontendに返すJSONには、描画に直接必要な `position` や `style` のみを含め、計算途中のスコアなどの内部データは含めません。
- **状態の永続化**: グラフのレイアウトやスタイル属性は、ツール実行のたびにデータベースに保存・更新されるため、状態が維持されます。
