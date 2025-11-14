# 正規化データモデルへの移行計画

## 1. 現状と課題

現在のシステムでは、ネットワークデータとその属性を以下のように管理しています：

- GraphMLコンテンツをそのまま`networks`テーブルの`graphml_content`列に格納
- ビジュアルマッピングや属性計算結果の保持が非構造化
- 属性検索や集計が困難
- 複数のネットワーク間での属性の再利用が困難

## 2. 目標とする正規化データモデル

シーケンス図（6.3.2）に記載されている通り、以下の正規化テーブルを導入します：

### 2.1 `attributes`テーブル

ネットワーク内の属性の**定義**を保持します。

```sql
CREATE TABLE attributes (
    id SERIAL PRIMARY KEY,
    network_id INTEGER NOT NULL REFERENCES networks(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- "numeric", "string", "boolean" etc.
    scope VARCHAR(10) NOT NULL, -- "node" or "edge"
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(network_id, name, scope)
);

-- インデックス
CREATE INDEX idx_attributes_network_id ON attributes(network_id);
```

### 2.2 `attribute_values`テーブル

属性の**値**を保持します。

```sql
CREATE TABLE attribute_values (
    id SERIAL PRIMARY KEY,
    attribute_id INTEGER NOT NULL REFERENCES attributes(id) ON DELETE CASCADE,
    element_id VARCHAR(255) NOT NULL, -- ノードまたはエッジのID
    value_numeric DOUBLE PRECISION,
    value_string TEXT,
    value_boolean BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(attribute_id, element_id)
);

-- インデックス
CREATE INDEX idx_attribute_values_attribute_id ON attribute_values(attribute_id);
CREATE INDEX idx_attribute_values_element_id ON attribute_values(element_id);
```

### 2.3 `visual_mapping_rules`テーブル

属性から視覚的表現へのマッピングルールを保持します。

```sql
CREATE TABLE visual_mapping_rules (
    id SERIAL PRIMARY KEY,
    network_id INTEGER NOT NULL REFERENCES networks(id) ON DELETE CASCADE,
    attribute_id INTEGER NOT NULL REFERENCES attributes(id) ON DELETE CASCADE,
    visual_property VARCHAR(50) NOT NULL, -- "node_size", "node_color", "edge_width", "edge_color"
    mapping_type VARCHAR(50) NOT NULL, -- "linear", "log", "categorical", etc.
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    color_scheme VARCHAR(255),
    config JSONB, -- その他の設定情報
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(network_id, visual_property)
);

-- インデックス
CREATE INDEX idx_visual_mapping_rules_network_id ON visual_mapping_rules(network_id);
CREATE INDEX idx_visual_mapping_rules_attribute_id ON visual_mapping_rules(attribute_id);
```

## 3. 段階的移行計画

### 3.1 第1段階：デュアルストレージフェーズ（2ヶ月）

この段階では、既存のGraphML保存とともに、新しい正規化テーブルへの書き込みを**両方実行**します。

1. 新しいテーブルとスキーマを作成（既存のデータには影響しない）
2. NetworkXMCPから属性計算結果を返す時、従来のGraphMLコンテンツに加えて、新たに抽出した属性の配列も返す
3. APIサービスで、受け取った属性データを正規化テーブルに書き込みつつ、GraphMLも従来通り保存
4. `/visdata`エンドポイントを拡張して、GraphMLからの読み込みと正規化テーブルからの読み込みの両方をサポート

この段階のメリット：
- 既存機能に影響を与えず、安全にデータを移行
- 問題が発生した場合は、従来のGraphMLデータから復元可能

### 3.2 第2段階：正規化優先フェーズ（3ヶ月）

この段階では、正規化テーブルを主データソースとし、GraphMLは補助的な役割に変更します。

1. `/visdata`エンドポイントを正規化テーブルからのみ読み込むように修正（高速化）
2. 新しいクエリAPI（例：`/network/{id}/attributes`、`/network/{id}/attributes/{name}/values`）を導入
3. 統計・分析APIを追加（例：`/network/{id}/metrics/summary`）
4. 既存の全GraphMLデータから属性を抽出し、正規化テーブルに移行するバッチジョブを実行

### 3.3 第3段階：完全正規化フェーズ（2ヶ月）

この段階では、GraphMLの保存を最小限にし、正規化テーブルをメインデータストレージとします。

1. NetworkXMCPを修正し、GraphML生成を最小限（エクスポート用途のみ）にする
2. 高度なクエリ機能（複数ネットワーク間の属性比較等）を実装
3. 可視化カスタマイズAPIの拡張（複数の属性から複合的なビジュアルマッピング等）
4. パフォーマンス最適化と機能拡張

## 4. 互換性確保とフォールバック戦略

- **GraphMLエクスポート機能の維持**: 正規化テーブルからGraphMLを動的に生成する機能は常に維持
- **バージョン管理**: API応答に`data_source_version`フィールドを含め、クライアントが処理を分岐可能に
- **段階的APIマイグレーション**: 古いAPIエンドポイントは一定期間維持し、徐々に非推奨化
- **ダウングレードスクリプト**: 問題発生時に正規化テーブルからGraphMLを再生成するツールを用意

## 5. 技術的実装詳細

### 5.1 GraphMLから属性データを抽出する関数

```python
def extract_attributes_from_graphml(graphml_content):
    """GraphMLから属性データを抽出する関数"""
    G = nx.read_graphml(io.StringIO(graphml_content))
    
    # 属性定義の抽出
    attributes = []
    
    # ノード属性
    node_attrs = set()
    for _, data in G.nodes(data=True):
        node_attrs.update(data.keys())
    
    for attr_name in node_attrs:
        if attr_name not in ['id', 'label']:  # 基本属性を除外
            attributes.append({
                'name': attr_name,
                'scope': 'node',
                'type': determine_attr_type(G.nodes, attr_name)
            })
    
    # エッジ属性
    edge_attrs = set()
    for _, _, data in G.edges(data=True):
        edge_attrs.update(data.keys())
    
    for attr_name in edge_attrs:
        if attr_name not in ['source', 'target']:  # 基本属性を除外
            attributes.append({
                'name': attr_name,
                'scope': 'edge',
                'type': determine_attr_type(G.edges, attr_name, is_edge=True)
            })
    
    # 属性値の抽出
    values = []
    for node_id, data in G.nodes(data=True):
        for attr_name, attr_value in data.items():
            if attr_name not in ['id', 'label']:
                values.append({
                    'element_id': node_id,
                    'attr_name': attr_name,
                    'scope': 'node',
                    'value': attr_value
                })
    
    for u, v, data in G.edges(data=True):
        edge_id = f"{u}_{v}"
        for attr_name, attr_value in data.items():
            if attr_name not in ['source', 'target']:
                values.append({
                    'element_id': edge_id,
                    'attr_name': attr_name,
                    'scope': 'edge',
                    'value': attr_value
                })
    
    return {
        'attribute_definitions': attributes,
        'attribute_values': values
    }
```

### 5.2 正規化テーブルからビジュアライゼーションデータを構築する関数

```python
def build_visualization_data_from_normalized_tables(network_id, db):
    """正規化テーブルからビジュアライゼーションデータを構築する関数"""
    # 1. ネットワーク基本構造の取得
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    
    # 最小限のGraphML解析で基本構造を取得
    G = nx.read_graphml(io.StringIO(network.graphml_content))
    
    # 2. 視覚マッピングルールの取得
    visual_rules = db.query(models.VisualMappingRule).filter(
        models.VisualMappingRule.network_id == network_id
    ).all()
    
    # 3. 属性と属性値の取得
    attributes = db.query(models.Attribute).filter(
        models.Attribute.network_id == network_id
    ).all()
    
    attr_dict = {attr.id: attr for attr in attributes}
    
    # 属性IDのリスト
    attr_ids = [attr.id for attr in attributes]
    
    # 一括で属性値を取得
    attr_values = db.query(models.AttributeValue).filter(
        models.AttributeValue.attribute_id.in_(attr_ids)
    ).all()
    
    # 属性値の整理（要素IDごと、属性IDごと）
    values_by_element = {}
    for val in attr_values:
        if val.element_id not in values_by_element:
            values_by_element[val.element_id] = {}
        
        attr = attr_dict[val.attribute_id]
        if attr.type == 'numeric':
            values_by_element[val.element_id][attr.name] = val.value_numeric
        elif attr.type == 'string':
            values_by_element[val.element_id][attr.name] = val.value_string
        elif attr.type == 'boolean':
            values_by_element[val.element_id][attr.name] = val.value_boolean
    
    # 4. ビジュアルマッピングルールの適用
    visual_property_mapping = {}
    for rule in visual_rules:
        attr = attr_dict[rule.attribute_id]
        visual_property_mapping[rule.visual_property] = {
            'attribute_name': attr.name,
            'mapping_type': rule.mapping_type,
            'min_value': rule.min_value,
            'max_value': rule.max_value,
            'color_scheme': rule.color_scheme,
            'config': rule.config
        }
    
    # 5. ノードとエッジの構築
    nodes = []
    for node_id, data in G.nodes(data=True):
        # 基本プロパティ
        node = {
            'id': node_id,
            'label': data.get('label', node_id)
        }
        
        # 座標
        if 'x' in data and 'y' in data:
            node['x'] = float(data['x'])
            node['y'] = float(data['y'])
        else:
            node['x'] = 0.0
            node['y'] = 0.0
        
        # デフォルト視覚プロパティ
        node['size'] = 5
        node['color'] = "#1d4ed8"
        
        # 属性値の追加
        if node_id in values_by_element:
            for attr_name, attr_value in values_by_element[node_id].items():
                node[attr_name] = attr_value
        
        # ビジュアルマッピングの適用
        apply_visual_mappings(node, visual_property_mapping, 'node')
        
        nodes.append(node)
    
    links = []
    for u, v, data in G.edges(data=True):
        # 基本プロパティ
        edge = {
            'source': u,
            'target': v,
        }
        
        # デフォルト視覚プロパティ
        edge['width'] = 1
        edge['color'] = "#cccccc"
        
        # エッジID
        edge_id = f"{u}_{v}"
        
        # 属性値の追加
        if edge_id in values_by_element:
            for attr_name, attr_value in values_by_element[edge_id].items():
                edge[attr_name] = attr_value
        
        # ビジュアルマッピングの適用
        apply_visual_mappings(edge, visual_property_mapping, 'edge')
        
        links.append(edge)
    
    return {
        'nodes': nodes,
        'links': links
    }
```

## 6. リスクと対策

| リスク | 対策 |
|---|---|
| 既存データの移行中の不整合 | デュアルストレージ期間を設け、整合性検証を徹底 |
| パフォーマンスへの影響 | 段階的に移行し、各段階でパフォーマンステストを実施 |
| API互換性の問題 | バージョンフラグを含め、クライアント側で分岐処理を可能に |
| 移行作業の複雑さ | 自動化スクリプトとテストを充実させ、正確性を確保 |
| ロールバックの必要性 | GraphMLを常にフォールバックとして維持 |

## 7. スケジュール

| フェーズ | 期間 | 主要タスク |
|---|---|---|
| 計画と準備 | 2週間 | スキーマ設計、移行ツール開発、テスト計画 |
| 第1段階：デュアルストレージ | 2ヶ月 | 新テーブル作成、両方への書き込み、整合性テスト |
| 第2段階：正規化優先 | 3ヶ月 | `/visdata`修正、新APIエンドポイント追加、データ移行 |
| 第3段階：完全正規化 | 2ヶ月 | GraphML最小化、高度機能追加、最適化 |
| 安定化と監視 | 1ヶ月 | パフォーマンス監視、バグ修正、ドキュメント更新 |

## 8. 結論

このデータモデル正規化により、ネットワークデータの構造をより柔軟かつ効率的に管理できるようになり、以下の利点が得られます：

- 属性ごとの効率的なクエリと集計
- 複数ネットワーク間での属性の再利用と比較
- 高度なビジュアルマッピングと分析機能
- パフォーマンスの向上と拡張性の確保

段階的な移行アプローチにより、リスクを最小限に抑えながら、システムを進化させることができます。