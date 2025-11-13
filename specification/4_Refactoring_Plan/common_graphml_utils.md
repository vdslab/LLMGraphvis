# GraphML処理ユーティリティ共通化設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトで使用するGraphML処理ユーティリティの共通化設計について説明します。現在、API側とNetworkXMCP側で重複しているGraphML処理コードを共通モジュールに抽出し、再利用性を高めることを目的としています。

## 現状の課題

1. **コードの重複**: API側とNetworkXMCP側で類似のGraphML処理コードが重複している
2. **一貫性の欠如**: 処理方法や例外処理が統一されていない
3. **機能拡張の困難**: 機能追加時に複数の場所を修正する必要がある
4. **テストの重複**: 同様の機能に対して複数のテストが必要

## 設計目標

1. **再利用性**: 共通のGraphML処理機能を提供する
2. **一貫性**: 統一された処理方法と例外処理を提供する
3. **拡張性**: 新しい機能を容易に追加できるようにする
4. **テスト容易性**: 単一の場所でテストを行えるようにする
5. **依存関係の明確化**: NetworkXへの依存関係を明確にする

## モジュール構造

```
common/
  utils/
    graphml/
      __init__.py        # モジュールのエクスポート
      parser.py          # GraphMLパース機能
      converter.py       # GraphML変換機能
      validator.py       # GraphML検証機能
      fixer.py           # GraphML修正機能
      serializer.py      # GraphMLシリアライズ機能
      types.py           # 型定義
      constants.py       # 定数定義
```

## 主要コンポーネント

### 1. パーサー (parser.py)

GraphMLファイルをパースし、内部表現に変換する機能を提供します。

```python
# common/utils/graphml/parser.py

import io
import logging
import networkx as nx
from typing import Dict, List, Any, Optional, Union, Tuple
from xml.etree import ElementTree as ET

from common.exceptions import GraphMLValidationError
from common.logging.config import get_logger
from .types import GraphData, NodeData, EdgeData, AttributeData
from .validator import validate_graphml_content

logger = get_logger("common.utils.graphml.parser")

def parse_graphml_to_networkx(
    graphml_content: str,
    validate: bool = True
) -> nx.Graph:
    """
    GraphML文字列をNetworkXグラフに変換する。
    
    Args:
        graphml_content: GraphML形式の文字列
        validate: GraphMLを検証するかどうか
        
    Returns:
        nx.Graph: NetworkXグラフ
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
    """
    if validate:
        validate_graphml_content(graphml_content)
    
    try:
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        return nx.read_graphml(content_io)
    except Exception as e:
        logger.error(f"Error parsing GraphML to NetworkX: {e}", exc_info=True)
        raise GraphMLValidationError(
            message=f"Failed to parse GraphML: {str(e)}",
            validation_errors=[{"error": str(e)}],
            context={"content_length": len(graphml_content)}
        )

def parse_graphml_to_data(
    graphml_content: str,
    validate: bool = True
) -> GraphData:
    """
    GraphML文字列をGraphDataオブジェクトに変換する。
    
    Args:
        graphml_content: GraphML形式の文字列
        validate: GraphMLを検証するかどうか
        
    Returns:
        GraphData: グラフデータ
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
    """
    G = parse_graphml_to_networkx(graphml_content, validate)
    
    # ノードデータの抽出
    nodes = []
    for node_id, attrs in G.nodes(data=True):
        node_data = NodeData(
            id=str(node_id),
            label=attrs.get("name", str(node_id)),
            attributes={}
        )
        
        # 位置情報の抽出
        if 'x' in attrs and 'y' in attrs:
            try:
                node_data.x = float(attrs['x'])
                node_data.y = float(attrs['y'])
            except (ValueError, TypeError):
                pass
        
        # サイズの抽出
        if 'size' in attrs:
            try:
                node_data.size = float(attrs['size'])
            except (ValueError, TypeError):
                pass
        
        # 色の抽出
        if 'color' in attrs:
            node_data.color = attrs['color']
        
        # その他の属性の抽出
        for key, value in attrs.items():
            if key not in ["id", "label", "x", "y", "size", "color", "name"]:
                node_data.attributes[key] = value
        
        nodes.append(node_data)
    
    # エッジデータの抽出
    edges = []
    for source, target, attrs in G.edges(data=True):
        edge_data = EdgeData(
            source=str(source),
            target=str(target),
            attributes={}
        )
        
        # 幅の抽出
        if 'width' in attrs:
            try:
                edge_data.width = float(attrs['width'])
            except (ValueError, TypeError):
                pass
        
        # 色の抽出
        if 'color' in attrs:
            edge_data.color = attrs['color']
        
        # その他の属性の抽出
        for key, value in attrs.items():
            if key not in ["source", "target", "width", "color"]:
                edge_data.attributes[key] = value
        
        edges.append(edge_data)
    
    # グラフ属性の抽出
    attributes = {}
    for key, value in G.graph.items():
        attributes[key] = value
    
    return GraphData(
        nodes=nodes,
        edges=edges,
        attributes=attributes,
        directed=G.is_directed()
    )

def extract_node_positions(
    graphml_content: str,
    validate: bool = True
) -> Dict[str, Dict[str, float]]:
    """
    GraphML文字列からノードの位置情報を抽出する。
    
    Args:
        graphml_content: GraphML形式の文字列
        validate: GraphMLを検証するかどうか
        
    Returns:
        Dict[str, Dict[str, float]]: ノードIDをキー、位置情報を値とする辞書
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
    """
    G = parse_graphml_to_networkx(graphml_content, validate)
    
    positions = {}
    for node, attrs in G.nodes(data=True):
        if 'x' in attrs and 'y' in attrs:
            try:
                positions[str(node)] = {
                    "x": float(attrs['x']),
                    "y": float(attrs['y'])
                }
            except (ValueError, TypeError):
                logger.warning(f"Invalid position for node {node}: x={attrs.get('x')}, y={attrs.get('y')}")
    
    return positions

def extract_node_attributes(
    graphml_content: str,
    attribute_name: str,
    validate: bool = True
) -> Dict[str, Any]:
    """
    GraphML文字列から指定された属性の値を抽出する。
    
    Args:
        graphml_content: GraphML形式の文字列
        attribute_name: 抽出する属性名
        validate: GraphMLを検証するかどうか
        
    Returns:
        Dict[str, Any]: ノードIDをキー、属性値を値とする辞書
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
    """
    G = parse_graphml_to_networkx(graphml_content, validate)
    
    attributes = {}
    for node, attrs in G.nodes(data=True):
        if attribute_name in attrs:
            attributes[str(node)] = attrs[attribute_name]
    
    return attributes
```

### 2. コンバーター (converter.py)

GraphMLファイルを標準形式に変換する機能を提供します。

```python
# common/utils/graphml/converter.py

import io
import logging
import networkx as nx
import random
from typing import Dict, List, Any, Optional, Union, Tuple
from xml.etree import ElementTree as ET

from common.exceptions import GraphMLValidationError, GraphProcessingError
from common.logging.config import get_logger
from .types import GraphData, NodeData, EdgeData, AttributeData
from .parser import parse_graphml_to_networkx
from .fixer import fix_graphml_structure
from .validator import validate_graphml_content

logger = get_logger("common.utils.graphml.converter")

def convert_to_standard_graphml(
    graphml_content: str,
    calculate_centrality: bool = True,
    fix_structure: bool = True,
    validate: bool = True
) -> str:
    """
    GraphML文字列を標準形式に変換する。
    
    Args:
        graphml_content: GraphML形式の文字列
        calculate_centrality: 中心性指標を計算するかどうか
        fix_structure: GraphML構造を修正するかどうか
        validate: GraphMLを検証するかどうか
        
    Returns:
        str: 標準形式のGraphML文字列
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
        GraphProcessingError: GraphMLの処理に失敗した場合
    """
    try:
        # GraphML構造の修正
        if fix_structure:
            graphml_content = fix_graphml_structure(graphml_content)
        
        # GraphMLの検証
        if validate:
            validate_graphml_content(graphml_content)
        
        # NetworkXグラフに変換
        G = parse_graphml_to_networkx(graphml_content, validate=False)
        
        # 中心性指標の計算
        if calculate_centrality and G.number_of_nodes() > 0:
            try:
                # 次数中心性
                degree_centrality = nx.degree_centrality(G)
                nx.set_node_attributes(G, degree_centrality, "degree_centrality")
                
                # 近接中心性
                closeness_centrality = nx.closeness_centrality(G)
                nx.set_node_attributes(G, closeness_centrality, "closeness_centrality")
                
                # 媒介中心性
                betweenness_centrality = nx.betweenness_centrality(G)
                nx.set_node_attributes(G, betweenness_centrality, "betweenness_centrality")
                
                # 固有ベクトル中心性
                try:
                    eigenvector_centrality = nx.eigenvector_centrality(G, max_iter=1000)
                except nx.PowerIterationFailedConvergence:
                    logger.warning("Eigenvector centrality did not converge, setting to 0.")
                    eigenvector_centrality = {node: 0.0 for node in G.nodes()}
                nx.set_node_attributes(G, eigenvector_centrality, "eigenvector_centrality")
            except Exception as e:
                logger.warning(f"Error calculating centrality: {e}")
        
        # 標準属性の設定
        for node in G.nodes():
            node_attrs = G.nodes[node]
            
            # 名前属性
            if 'name' not in node_attrs:
                for alt_attr in ['label', 'id', 'title', 'node_name', 'node_label']:
                    if alt_attr in node_attrs:
                        node_attrs['name'] = str(node_attrs[alt_attr])
                        break
                else:
                    node_attrs['name'] = f"Node {node}"
            else:
                node_attrs['name'] = str(node_attrs['name'])
            
            # 色属性
            if 'color' not in node_attrs:
                for alt_attr in ['colour', 'node_color', 'fill_color', 'fill', 'rgb', 'hex']:
                    if alt_attr in node_attrs:
                        node_attrs['color'] = str(node_attrs[alt_attr])
                        break
                else:
                    node_attrs['color'] = "#1d4ed8"  # デフォルト色
            else:
                node_attrs['color'] = str(node_attrs['color'])
            
            # サイズ属性
            if 'size' not in node_attrs:
                for alt_attr in ['node_size', 'width', 'radius', 'scale']:
                    if alt_attr in node_attrs:
                        node_attrs['size'] = str(node_attrs[alt_attr])
                        break
                else:
                    node_attrs['size'] = "5.0"  # デフォルトサイズ
            else:
                node_attrs['size'] = str(node_attrs['size'])
            
            # 位置情報
            if 'x' not in node_attrs:
                for alt_attr in ['pos_x', 'position_x', 'coord_x', 'coordinate_x']:
                    if alt_attr in node_attrs:
                        node_attrs['x'] = str(node_attrs[alt_attr])
                        break
                else:
                    node_attrs['x'] = str(random.uniform(-1.0, 1.0))
            else:
                node_attrs['x'] = str(node_attrs['x'])
            
            if 'y' not in node_attrs:
                for alt_attr in ['pos_y', 'position_y', 'coord_y', 'coordinate_y']:
                    if alt_attr in node_attrs:
                        node_attrs['y'] = str(node_attrs[alt_attr])
                        break
                else:
                    node_attrs['y'] = str(random.uniform(-1.0, 1.0))
            else:
                node_attrs['y'] = str(node_attrs['y'])
        
        # エッジの標準属性の設定
        for u, v, data in G.edges(data=True):
            # 幅属性
            if 'width' not in data:
                data['width'] = "1.0"
            else:
                data['width'] = str(data['width'])
            
            # 色属性
            if 'color' not in data:
                data['color'] = "#94a3b8"
            else:
                data['color'] = str(data['color'])
        
        # グラフレベルの属性を設定
        G.graph['node_default_size'] = "5.0"
        G.graph['node_default_color'] = "#1d4ed8"
        G.graph['edge_default_width'] = "1.0"
        G.graph['edge_default_color'] = "#94a3b8"
        G.graph['graph_format_version'] = "1.0"
        G.graph['graph_format_type'] = "standardized_graphml"
        
        # GraphMLに変換
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        standardized_graphml = output.read().decode("utf-8")
        
        return standardized_graphml
    except GraphMLValidationError:
        # 検証エラーはそのまま再送
        raise
    except Exception as e:
        logger.error(f"Error converting GraphML: {e}", exc_info=True)
        raise GraphProcessingError(
            message=f"Failed to convert GraphML: {str(e)}",
            context={"content_length": len(graphml_content)}
        )

def add_layout_to_graphml(
    graphml_content: str,
    positions: Dict[str, Dict[str, float]],
    validate: bool = True
) -> str:
    """
    GraphML文字列にレイアウト情報を追加する。
    
    Args:
        graphml_content: GraphML形式の文字列
        positions: ノードIDをキー、位置情報を値とする辞書
        validate: GraphMLを検証するかどうか
        
    Returns:
        str: レイアウト情報を追加したGraphML文字列
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
        GraphProcessingError: GraphMLの処理に失敗した場合
    """
    try:
        # GraphMLの検証
        if validate:
            validate_graphml_content(graphml_content)
        
        # NetworkXグラフに変換
        G = parse_graphml_to_networkx(graphml_content, validate=False)
        
        # 位置情報を設定
        for node_id, pos in positions.items():
            if node_id in G.nodes:
                G.nodes[node_id]['x'] = str(pos.get('x', 0.0))
                G.nodes[node_id]['y'] = str(pos.get('y', 0.0))
        
        # GraphMLに変換
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        updated_graphml = output.read().decode("utf-8")
        
        return updated_graphml
    except GraphMLValidationError:
        # 検証エラーはそのまま再送
        raise
    except Exception as e:
        logger.error(f"Error adding layout to GraphML: {e}", exc_info=True)
        raise GraphProcessingError(
            message=f"Failed to add layout to GraphML: {str(e)}",
            context={"content_length": len(graphml_content)}
        )

def add_attributes_to_graphml(
    graphml_content: str,
    node_attributes: Dict[str, Dict[str, Any]],
    edge_attributes: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
    graph_attributes: Optional[Dict[str, Any]] = None,
    validate: bool = True
) -> str:
    """
    GraphML文字列に属性情報を追加する。
    
    Args:
        graphml_content: GraphML形式の文字列
        node_attributes: ノードIDをキー、属性辞書を値とする辞書
        edge_attributes: (ソースID, ターゲットID)をキー、属性辞書を値とする辞書
        graph_attributes: グラフ属性の辞書
        validate: GraphMLを検証するかどうか
        
    Returns:
        str: 属性情報を追加したGraphML文字列
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
        GraphProcessingError: GraphMLの処理に失敗した場合
    """
    try:
        # GraphMLの検証
        if validate:
            validate_graphml_content(graphml_content)
        
        # NetworkXグラフに変換
        G = parse_graphml_to_networkx(graphml_content, validate=False)
        
        # ノード属性を設定
        for node_id, attrs in node_attributes.items():
            if node_id in G.nodes:
                for key, value in attrs.items():
                    G.nodes[node_id][key] = value
        
        # エッジ属性を設定
        if edge_attributes:
            for (source, target), attrs in edge_attributes.items():
                if G.has_edge(source, target):
                    for key, value in attrs.items():
                        G[source][target][key] = value
        
        # グラフ属性を設定
        if graph_attributes:
            for key, value in graph_attributes.items():
                G.graph[key] = value
        
        # GraphMLに変換
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        updated_graphml = output.read().decode("utf-8")
        
        return updated_graphml
    except GraphMLValidationError:
        # 検証エラーはそのまま再送
        raise
    except Exception as e:
        logger.error(f"Error adding attributes to GraphML: {e}", exc_info=True)
        raise GraphProcessingError(
            message=f"Failed to add attributes to GraphML: {str(e)}",
            context={"content_length": len(graphml_content)}
        )
```

### 3. バリデーター (validator.py)

GraphMLファイルの検証機能を提供します。

```python
# common/utils/graphml/validator.py

import io
import logging
import networkx as nx
from typing import Dict, List, Any, Optional
from xml.etree import ElementTree as ET

from common.exceptions import GraphMLValidationError
from common.logging.config import get_logger
from .constants import GRAPHML_NAMESPACE

logger = get_logger("common.utils.graphml.validator")

def validate_graphml_content(graphml_content: str) -> bool:
    """
    GraphML文字列を検証する。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        bool: 検証に成功した場合はTrue
        
    Raises:
        GraphMLValidationError: GraphMLの検証に失敗した場合
    """
    validation_errors = []
    
    # 空のコンテンツをチェック
    if not graphml_content or not isinstance(graphml_content, str):
        raise GraphMLValidationError(
            message="Empty or invalid GraphML content",
            validation_errors=[{"error": "Empty or invalid GraphML content"}]
        )
    
    # 基本的なXML構造をチェック
    if "<graphml" not in graphml_content:
        validation_errors.append({
            "error": "Missing <graphml> element",
            "description": "GraphML file must contain a <graphml> element"
        })
    
    if "<graph" not in graphml_content:
        validation_errors.append({
            "error": "Missing <graph> element",
            "description": "GraphML file must contain a <graph> element"
        })
    
    # XMLとしての妥当性をチェック
    try:
        ET.fromstring(graphml_content)
    except Exception as e:
        validation_errors.append({
            "error": f"Invalid XML: {str(e)}",
            "description": "GraphML file must be valid XML"
        })
    
    # NetworkXでのパースをチェック
    if not validation_errors:
        try:
            content_io = io.BytesIO(graphml_content.encode('utf-8'))
            nx.read_graphml(content_io)
        except Exception as e:
            validation_errors.append({
                "error": f"NetworkX parsing error: {str(e)}",
                "description": "GraphML file must be parsable by NetworkX"
            })
    
    # 検証エラーがある場合は例外を発生
    if validation_errors:
        raise GraphMLValidationError(
            message="GraphML validation failed",
            validation_errors=validation_errors,
            context={"content_length": len(graphml_content)}
        )
    
    return True

def validate_graphml_structure(graphml_content: str) -> List[Dict[str, str]]:
    """
    GraphML文字列の構造を検証し、警告を返す。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        List[Dict[str, str]]: 警告のリスト
    """
    warnings = []
    
    # XMLとしてパース
    try:
        root = ET.fromstring(graphml_content)
        
        # 名前空間をチェック
        if not root.tag.startswith("{" + GRAPHML_NAMESPACE + "}"):
            warnings.append({
                "warning": "Missing or incorrect GraphML namespace",
                "description": f"Expected namespace: {GRAPHML_NAMESPACE}"
            })
        
        # <key>要素をチェック
        key_elements = root.findall(".//{" + GRAPHML_NAMESPACE + "}key")
        if not key_elements:
            warnings.append({
                "warning": "Missing <key> elements",
                "description": "GraphML file should contain <key> elements for node and edge attributes"
            })
        
        # <graph>要素のedgedefault属性をチェック
        graph_elements = root.findall(".//{" + GRAPHML_NAMESPACE + "}graph")
        for graph in graph_elements:
            if "edgedefault" not in graph.attrib:
                warnings.append({
                    "warning": "Missing edgedefault attribute in <graph> element",
                    "description": "The <graph> element should have an edgedefault attribute"
                })
    except Exception as e:
        warnings.append({
            "warning": f"Could not parse XML for structure validation: {str(e)}",
            "description": "GraphML file should be valid XML"
        })
    
    return warnings
```

### 4. フィクサー (fixer.py)

GraphMLファイルの修正機能を提供します。

```python
# common/utils/graphml/fixer.py

import re
import logging
from typing import Dict, List, Any, Optional
from xml.sax.saxutils import escape

from common.logging.config import get_logger
from .constants import GRAPHML_NAMESPACE

logger = get_logger("common.utils.graphml.fixer")

def fix_graphml_structure(graphml_content: str) -> str:
    """
    GraphML文字列の構造を修正する。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        str: 修正されたGraphML文字列
    """
    logger.debug("Fixing GraphML structure")
    
    try:
        # XMLヘッダーが欠けている場合は追加
        if "<?xml" not in graphml_content:
            logger.debug("Adding XML header")
            graphml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + graphml_content
        
        # 名前空間宣言が欠けている場合は追加
        if "<graphml" in graphml_content and "xmlns=" not in graphml_content:
            logger.debug("Adding namespace declarations")
            graphml_content = re.sub(
                r"(<graphml)",
                r'\1 xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd" ',
                graphml_content,
                count=1
            )
        
        # <graph>要素にedgedefault属性が欠けている場合は追加
        if "<graph" in graphml_content and "edgedefault=" not in graphml_content:
            logger.debug("Adding edgedefault attribute to graph element")
            graphml_content = re.sub(
                r"(<graph[^>]*>)",
                r'\1 edgedefault="undirected" ',
                graphml_content,
                count=1
            )
        
        # 不正なXML文字を削除
        illegal_xml_chars = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
        if illegal_xml_chars.search(graphml_content):
            logger.debug("Removing illegal XML characters")
            graphml_content = illegal_xml_chars.sub('', graphml_content)
        
        # XMLの閉じタグが不完全な場合の修正を試みる
        # graphmlタグの確認
        if "<graphml" in graphml_content and "</graphml>" not in graphml_content:
            logger.debug("Adding missing </graphml> tag")
            graphml_content += "\n</graphml>"
        
        # graphタグの確認
        if "<graph" in graphml_content and "</graph>" not in graphml_content:
            # </graphml>の前に</graph>を挿入
            if "</graphml>" in graphml_content:
                logger.debug("Adding missing </graph> tag before </graphml>")
                graphml_content = graphml_content.replace("</graphml>", "</graph>\n</graphml>")
            else:
                logger.debug("Adding missing </graph> tag at the end")
                graphml_content += "\n</graph>"
        
        # データノードの修正 - 自己閉じタグに変換
        if "<data " in graphml_content and "</data>" not in graphml_content:
            logger.debug("Fixing data elements to self-closing tags if needed")
            # <data key="xxx"></data> -> <data key="xxx"/>
            graphml_content = re.sub(r'<data key="([^"]+)"></data>', r'<data key="\1"/>', graphml_content)
    except Exception as e:
        logger.error(f"Error while fixing GraphML structure: {e}")
        # エラーが発生しても元のコンテンツを返す
    
    return graphml_content

def add_missing_attributes(graphml_content: str) -> str:
    """
    GraphML文字列に不足している属性を追加する。
    
    Args:
        graphml_content: GraphML形式の文字列
        
    Returns:
        str: 属性が追加されたGraphML文字列
    """
    # <key>要素を追加するためのリスト
    key_elements = [
        '<key id="d0" for="node" attr.name="name" attr.type="string"/>',
        '<key id="d1" for="node" attr.name="size" attr.type="double"/>',
        '<key id="d2" for="node" attr.name="color" attr.type="string"/>',
        '<key id="d3" for="node" attr.name="description" attr.type="string"/>',
        '<key id="d4" for="node" attr