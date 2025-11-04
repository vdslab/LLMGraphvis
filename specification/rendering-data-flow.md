## LLM Function Callingによるレンダリングデータ生成フロー

本ドキュメントは、ユーザーの自然言語指示に基づき、LLMの**Function Calling**機能を利用して動的にネットワークのレンダリングデータを生成・更新する一連の処理フローを定義します。このフローは、[主要な処理フロー](./Interactions.md)のシーケンス図で示されるやり取りを、データの流れと責務の観点から詳細に記述したものです。

### 概要

ユーザーが「次数が多いノードを大きくして」のような曖昧な指示を出すと、システムは以下の手順でレンダリングデータを更新します。

1.  **Backend**がユーザーの指示を受け取り、LLMに送信します。
2.  **LLM**は、指示を解釈し、まずネットワークの現状を把握するために `list_attributes` ツールの呼び出しを要求します。
3.  **Backend**はツールを実行し、現在の属性リスト（例: `['weight']`）をLLMに返します。
4.  **LLM**は、必要な属性（`degree_centrality`）が存在しないことを確認し、次に `calculate_centrality` ツールの呼び出しを要求します。
5.  **Backend**はツールを実行し、計算結果がDBに保存されたことをLLMに報告します。
6.  **LLM**は、属性の準備ができたことを確認し、最後に `apply_metric_to_visual` ツールを呼び出して、属性と視覚的特徴（ノードサイズ）を紐付けるルールを作成させます。
7.  **Backend**はツールを実行してマッピングルールをDBに保存し、Frontendにネットワークの更新を通知します。
8.  **Frontend**は通知を受けて、最終的なレンダリングデータを要求し、BackendはDBから全ての情報を動的に組み立てて返却します。

### データフローと責務

#### 1. LLMによる複数ステップのツールプランニング

BackendとLLMは、以下のような複数回のやり取りを通じて、段階的にタスクを実行します。

- **1回目のLLM呼び出し**:
    - **Backend → LLM**: ユーザー指示 `「友達が多い人を大きく表示して」` + ツールリスト
    - **LLM → Backend**: `list_attributes()` の呼び出しを要求

- **2回目のLLM呼び出し**:
    - **Backend → LLM**: `list_attributes` の実行結果 `['weight']`
    - **LLM → Backend**: `calculate_centrality(type: "degree")` の呼び出しを要求

- **3回目のLLM呼び出し**:
    - **Backend → LLM**: `calculate_centrality` の実行成功
    - **LLM → Backend**: `apply_metric_to_visual(metric: "degree_centrality", visual: "node_size", mapping: {scale: 'linear', ...})` の呼び出しを要求

#### 2. Backendによるツール実行と永続化

Backendは、LLMの要求に従ってNetworkXMCPのAPIを呼び出し、結果を正規化されたテーブルに永続化します。

- `GET /tools/list_attributes`: `attributes`テーブルから属性名の一覧を取得します。
- `POST /tools/calculate_centrality`: 計算結果を`attributes`および`attribute_values`テーブルに書き込みます。
- `POST /tools/apply_metric_to_visual`: マッピングルールを`visual_mapping_rules`テーブルに書き込みます。

#### 3. Backendによる動的なレンダリングデータ生成

Frontendが `/network/{network_id}/visdata` を呼び出すと、Backendはリクエストの都度、以下の情報をDBから読み込み、最終的なレンダリングデータを動的に組み立てて返します。

1.  `networks`テーブルから元のネットワーク構造
2.  `attributes`と`attribute_values`テーブルから全ての属性データ（座標を含む）
3.  `visual_mapping_rules`テーブルから適用すべき視覚ルール

Backend（またはBackendから依頼されたNetworkXMCP）は、これらの情報を統合し、各ノード・エッジのスタイルを決定して最終的なJSONを生成します。

### 設計上の要点

*   **責務の分離**:

    *   **LLM**: 自然言語を構造化されたツールコールに**変換**する。

    *   **NetworkXMCP**: ネットワークに関する**計算**と**属性・ルールの永続化**に特化する。

    *   **Backend**: LLMとツールの**オーケストレーション**と、リクエストに応じた**永続化された属性と視覚ルールからの動的なレンダリングデータの組み立て**、およびFrontendへの返却を行う。

*   **状態の分離**:

    *   ネットワークの**構造** (`networks`)、**属性** (`attributes`, `attribute_values`)、**視覚ルール** (`visual_mapping_rules`) はそれぞれ独立して永続化されます。

    *   最終的なレンダリングデータ（視覚表現）は永続化されず、これらの永続化されたデータから都度生成されます。これにより、状態の不整合を防ぎ、柔軟なデータ操作を可能にします。
