"""
ネットワーク操作ツールモジュール
===================

NetworkXを使用したグラフの操作ツールを提供します。
"""

import networkx as nx
import numpy as np
import logging
import io
import random
from typing import Dict, List, Any, Optional, Union

# ロギングの設定
logger = logging.getLogger("networkx_mcp.tools.network")

def create_random_network(num_nodes=20, edge_probability=0.2, seed=None):
    """
    ランダムネットワークを作成する
    
    Args:
        num_nodes (int, optional): ノード数
        edge_probability (float, optional): エッジ確率
        seed (int, optional): 乱数シード
        
    Returns:
        tuple: (NetworkXグラフ, ノードリスト, エッジリスト)
    """
    try:
        # 乱数シードの設定
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # ランダムグラフを生成
        G = nx.gnp_random_graph(num_nodes, edge_probability, seed=seed)
        
        # 連結グラフを確保（孤立ノードがないようにする）
        if not nx.is_connected(G):
            # 連結成分を取得
            components = list(nx.connected_components(G))
            # 最大の連結成分以外の各成分から、最大成分へエッジを追加
            largest_component = max(components, key=len)
            for component in components:
                if component != largest_component:
                    # 各成分から最大成分へのエッジを追加
                    node_from = random.choice(list(component))
                    node_to = random.choice(list(largest_component))
                    G.add_edge(node_from, node_to)
        
        # ノードとエッジの情報を抽出
        nodes = []
        for node in G.nodes():
            # ノードごとに少し異なるサイズと色の変化をつける
            size_variation = random.uniform(4.5, 5.5)
            color_variation = random.randint(-15, 15)
            base_color = [29, 78, 216]  # #1d4ed8のRGB値
            
            # 色の変化を適用（範囲内に収める）
            r = max(0, min(255, base_color[0] + color_variation))
            g = max(0, min(255, base_color[1] + color_variation))
            b = max(0, min(255, base_color[2] + color_variation))
            
            nodes.append({
                "id": str(node),
                "label": f"Node {node}",
                "size": size_variation,
                "color": f"rgb({r}, {g}, {b})"
            })
        
        edges = []
        for edge in G.edges():
            edges.append({
                "source": str(edge[0]),
                "target": str(edge[1]),
                "width": 1,
                "color": "#94a3b8"
            })
        
        # スプリングレイアウトを適用
        pos = nx.spring_layout(G)
        
        # ノードの位置情報を追加
        for node in nodes:
            node_id = int(node["id"])
            if node_id in pos:
                node["x"] = float(pos[node_id][0])
                node["y"] = float(pos[node_id][1])
        
        return G, nodes, edges
    except Exception as e:
        logger.error(f"Error creating random network: {e}")
        return None, [], []

def parse_graphml_string(graphml_content):
    """
    GraphML文字列をパースしてNetworkXグラフとノード・エッジ情報を抽出する
    
    Args:
        graphml_content (str): GraphML文字列
        
    Returns:
        dict: 処理結果を含む辞書
    """
    try:
        # Parse the GraphML content
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)
        
        # Extract nodes and edges
        nodes = []
        for node in G.nodes(data=True):
            node_id = str(node[0])
            attrs = node[1]
            
            node_data = {
                "id": node_id,
                "label": attrs.get("name", node_id)
            }
            
            # Add position if available
            if 'x' in attrs and 'y' in attrs:
                try:
                    node_data['x'] = float(attrs['x'])
                    node_data['y'] = float(attrs['y'])
                except (ValueError, TypeError):
                    pass
            
            # Add size if available
            if 'size' in attrs:
                try:
                    node_data['size'] = float(attrs['size'])
                except (ValueError, TypeError):
                    node_data['size'] = 5.0
            
            # Add color if available
            if 'color' in attrs:
                node_data['color'] = attrs['color']
            
            # Add any additional node attributes
            for key, value in attrs.items():
                if key not in ["id", "label", "x", "y", "size", "color"]:
                    node_data[key] = value
            
            nodes.append(node_data)
        
        edges = []
        for edge in G.edges(data=True):
            source = str(edge[0])
            target = str(edge[1])
            attrs = edge[2]
            
            edge_data = {
                "source": source,
                "target": target
            }
            
            # Add width if available
            if 'width' in attrs:
                try:
                    edge_data['width'] = float(attrs['width'])
                except (ValueError, TypeError):
                    pass
            
            # Add color if available
            if 'color' in attrs:
                edge_data['color'] = attrs['color']
            
            # Add any additional edge attributes
            for key, value in attrs.items():
                if key not in ["source", "target", "width", "color"]:
                    edge_data[key] = value
            
            edges.append(edge_data)
        
        return {
            "success": True,
            "graph": G,
            "nodes": nodes,
            "edges": edges
        }
    except Exception as e:
        logger.error(f"Error parsing GraphML string: {e}")
        return {
            "success": False,
            "error": f"Error parsing GraphML string: {str(e)}"
        }

def fix_graphml_structure(graphml_content):
    """
    GraphMLの構造を修正する
    
    Args:
        graphml_content (str): GraphML文字列
        
    Returns:
        str: 修正されたGraphML文字列
    """
    # デバッグログ
    logger.debug("Fixing GraphML structure")
    
    # 全体的な修正作業をトライ
    try:
        # XMLヘッダーが欠けている場合は追加
        if "<?xml" not in graphml_content:
            logger.debug("Adding XML header")
            graphml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + graphml_content
        
        # 名前空間宣言が欠けている場合は追加
        if "<graphml" in graphml_content and "xmlns=" not in graphml_content:
            logger.debug("Adding namespace declarations")
            graphml_content = graphml_content.replace(
                "<graphml", 
                '<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"'
            )
        
        # <graph>要素にedgedefault属性が欠けている場合は追加
        if "<graph" in graphml_content and "edgedefault=" not in graphml_content:
            logger.debug("Adding edgedefault attribute to graph element")
            graphml_content = graphml_content.replace(
                "<graph", 
                '<graph edgedefault="undirected"'
            )
        
        # 不正なXML文字を削除
        import re
        # XMLの不正な文字を削除するパターン
        # XMLで使用できない文字のパターン
        illegal_xml_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
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

def convert_to_standard_graphml(graphml_content):
    """
    あらゆるGraphMLデータを標準形式に変換し、主要な中心性指標を計算して属性として追加する
    
    Args:
        graphml_content (str): GraphML文字列
        
    Returns:
        dict: 処理結果を含む辞書
    """
    try:
        # デバッグ情報を記録
        logger.debug(f"Converting GraphML content: {graphml_content[:100]}...")
        
        # 入力チェック
        if not graphml_content or not isinstance(graphml_content, str):
            logger.error("Invalid GraphML content: empty or not a string")
            return {
                "success": False,
                "error": "Invalid GraphML content: empty or not a string"
            }
        
        # 最小限のGraphML構造チェック
        if "<graph" not in graphml_content:
            logger.error("Invalid GraphML content: missing <graph> element")
            return {
                "success": False,
                "error": "Invalid GraphML content: missing <graph> element. GraphML file must contain a <graph> element."
            }
        
        # デバッグ情報を追加
        logger.debug(f"GraphML content before fixing: {graphml_content[:500]}...")
        
        # GraphML構造を修正
        fixed_graphml = fix_graphml_structure(graphml_content)
        
        # デバッグ情報を追加
        logger.debug(f"GraphML content after fixing: {fixed_graphml[:500]}...")
        
        # Parse the GraphML content with better error handling
        try:
            content_io = io.BytesIO(fixed_graphml.encode('utf-8'))
            G = nx.read_graphml(content_io)
            logger.debug(f"Successfully parsed GraphML with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        except Exception as parse_error:
            logger.error(f"Error parsing GraphML: {parse_error}")
            # より詳細なエラー情報を提供
            error_details = str(parse_error)
            if "XML" in error_details:
                # XMLエラーが発生した場合、さらに修正を試みる
                try:
                    logger.debug("Attempting additional XML fixes...")
                    # XMLの基本構造を確認し修正
                    if not fixed_graphml.strip().startswith('<?xml'):
                        fixed_graphml = '<?xml version="1.0" encoding="UTF-8"?>\n' + fixed_graphml
                    
                    # 再度パースを試みる
                    content_io = io.BytesIO(fixed_graphml.encode('utf-8'))
                    G = nx.read_graphml(content_io)
                    logger.debug(f"Successfully parsed GraphML after XML fixes with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
                except Exception as second_parse_error:
                    logger.error(f"Error parsing GraphML after XML fixes: {second_parse_error}")
                    return {
                        "success": False,
                        "error": f"Invalid XML in GraphML file that could not be fixed: {error_details}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to parse GraphML: {error_details}"
                }
        
        # 主要な中心性指標を計算
        logger.debug("Calculating centrality metrics...")
        try:
            if G.number_of_nodes() > 0:
                degree_centrality = nx.degree_centrality(G)
                closeness_centrality = nx.closeness_centrality(G)
                betweenness_centrality = nx.betweenness_centrality(G)
                
                # 固有ベクトル中心性は収束しないことがあるため、例外処理を追加
                try:
                    eigenvector_centrality = nx.eigenvector_centrality_numpy(G, max_iter=1000)
                except nx.PowerIterationFailedConvergence:
                    logger.warning("Eigenvector centrality did not converge, setting to 0.")
                    eigenvector_centrality = {node: 0.0 for node in G.nodes()}

                # 計算した中心性をノード属性として設定
                nx.set_node_attributes(G, degree_centrality, "degree_centrality")
                nx.set_node_attributes(G, closeness_centrality, "closeness_centrality")
                nx.set_node_attributes(G, betweenness_centrality, "betweenness_centrality")
                nx.set_node_attributes(G, eigenvector_centrality, "eigenvector_centrality")
                logger.debug("Successfully calculated and set centrality attributes.")
            else:
                logger.debug("Graph has no nodes, skipping centrality calculation.")

        except Exception as centrality_error:
            logger.error(f"Error calculating centrality: {centrality_error}")
            # 中心性計算でエラーが発生しても、処理は続行する
            pass

        # 既存の属性を確認し、標準属性名へのマッピングを検出
        attribute_mapping = {
            'name': ['name', 'label', 'id', 'title', 'node_name', 'node_label'],
            'color': ['color', 'colour', 'node_color', 'fill_color', 'fill', 'rgb', 'hex'],
            'size': ['size', 'node_size', 'width', 'radius', 'scale'],
            'description': ['description', 'desc', 'note', 'info', 'detail', 'tooltip']
        }
        
        # 各ノードに標準属性を追加
        logger.debug("Adding standard attributes to nodes")
        for node in G.nodes():
            node_str = str(node)
            node_attrs = G.nodes[node]
            
            # 名前属性の処理
            if 'name' not in node_attrs:
                # 代替属性を探す
                for alt_attr in attribute_mapping['name']:
                    if alt_attr in node_attrs and alt_attr != 'name':
                        node_attrs['name'] = str(node_attrs[alt_attr])
                        break
                else:
                    # 代替属性が見つからない場合はノードIDを使用
                    node_attrs['name'] = f"Node {node_str}"
            else:
                # 既存の属性を文字列に変換
                node_attrs['name'] = str(node_attrs['name'])
            
            # 色属性の処理
            if 'color' not in node_attrs:
                # 代替属性を探す
                for alt_attr in attribute_mapping['color']:
                    if alt_attr in node_attrs and alt_attr != 'color':
                        node_attrs['color'] = str(node_attrs[alt_attr])
                        break
                else:
                    # 代替属性が見つからない場合はデフォルト色を使用
                    node_attrs['color'] = "#1d4ed8"  # Default color
            else:
                # 既存の属性を文字列に変換
                node_attrs['color'] = str(node_attrs['color'])
            
            # サイズ属性の処理
            if 'size' not in node_attrs:
                # 代替属性を探す
                for alt_attr in attribute_mapping['size']:
                    if alt_attr in node_attrs and alt_attr != 'size':
                        node_attrs['size'] = str(node_attrs[alt_attr])
                        break
                else:
                    # 代替属性が見つからない場合はデフォルトサイズを使用
                    node_attrs['size'] = "5.0"  # Default size
            else:
                # 既存の属性を文字列に変換
                node_attrs['size'] = str(node_attrs['size'])
            
            # 説明属性の処理
            if 'description' not in node_attrs:
                # 代替属性を探す
                for alt_attr in attribute_mapping['description']:
                    if alt_attr in node_attrs and alt_attr != 'description':
                        node_attrs['description'] = str(node_attrs[alt_attr])
                        break
                else:
                    # 代替属性が見つからない場合はデフォルト説明を使用
                    node_attrs['description'] = f"Node {node_str}"
            else:
                # 既存の属性を文字列に変換
                node_attrs['description'] = str(node_attrs['description'])
                
            # 位置情報（x, y座標）の処理
            # x座標の処理
            if 'x' not in node_attrs:
                # 代替属性を探す
                for alt_attr in ['x', 'pos_x', 'position_x', 'coord_x', 'coordinate_x']:
                    if alt_attr in node_attrs:
                        node_attrs['x'] = str(node_attrs[alt_attr])
                        break
                else:
                    # 代替属性が見つからない場合はランダムな位置を生成
                    import random
                    node_attrs['x'] = str(random.uniform(-1.0, 1.0))
            else:
                # 既存の属性を文字列に変換
                node_attrs['x'] = str(node_attrs['x'])
                
            # y座標の処理
            if 'y' not in node_attrs:
                # 代替属性を探す
                for alt_attr in ['y', 'pos_y', 'position_y', 'coord_y', 'coordinate_y']:
                    if alt_attr in node_attrs:
                        node_attrs['y'] = str(node_attrs[alt_attr])
                        break
                else:
                    # 代替属性が見つからない場合はランダムな位置を生成
                    import random
                    node_attrs['y'] = str(random.uniform(-1.0, 1.0))
            else:
                # 既存の属性を文字列に変換
                node_attrs['y'] = str(node_attrs['y'])
        
        # <key>要素を追加するためのリスト
        key_elements = [
            '<key id="d0" for="node" attr.name="name" attr.type="string"/>',
            '<key id="d1" for="node" attr.name="size" attr.type="double"/>',
            '<key id="d2" for="node" attr.name="color" attr.type="string"/>',
            '<key id="d3" for="node" attr.name="description" attr.type="string"/>',
            '<key id="d4" for="node" attr.name="x" attr.type="double"/>',
            '<key id="d5" for="node" attr.name="y" attr.type="double"/>',
            '<key id="d6" for="edge" attr.name="width" attr.type="string"/>',
            '<key id="d7" for="edge" attr.name="color" attr.type="string"/>',
            '<key id="d8" for="node" attr.name="degree_centrality" attr.type="double"/>',
            '<key id="d9" for="node" attr.name="closeness_centrality" attr.type="double"/>',
            '<key id="d10" for="node" attr.name="betweenness_centrality" attr.type="double"/>',
            '<key id="d11" for="node" attr.name="eigenvector_centrality" attr.type="double"/>',
        ]
        
        # グラフレベルの属性を追加
        logger.debug("Adding graph-level attributes")
        G.graph['node_default_size'] = "5.0"
        G.graph['node_default_color'] = "#1d4ed8"
        G.graph['edge_default_width'] = "1.0"
        G.graph['edge_default_color'] = "#94a3b8"
        G.graph['graph_format_version'] = "1.0"
        G.graph['graph_format_type'] = "standardized_graphml"
        
        # エッジにも標準的な属性を追加
        logger.debug("Adding standard attributes to edges")
        for u, v, data in G.edges(data=True):
            if 'width' not in data:
                data['width'] = "1.0"
            else:
                # 既存の属性を文字列に変換
                data['width'] = str(data['width'])
                
            if 'color' not in data:
                data['color'] = "#94a3b8"
            else:
                # 既存の属性を文字列に変換
                data['color'] = str(data['color'])
        
        # 標準化されたGraphMLにエクスポート
        try:
            logger.debug("Exporting to standardized GraphML format")
            # エクスポート前にノードとエッジの属性が文字列型であることを確認
            for node, attrs in G.nodes(data=True):
                for key, value in list(attrs.items()):
                    if value is not None:
                        try:
                            # 数値型はそのまま（write_graphmlが処理する）
                            if not isinstance(value, (int, float)):
                                attrs[key] = str(value)
                        except Exception as e:
                            logger.warning(f"属性変換エラー (ノード {node}, 属性 {key}): {e}")
                            attrs[key] = f"Value-{key}"
                        
            for u, v, attrs in G.edges(data=True):
                for key, value in list(attrs.items()):
                    if value is not None:
                        try:
                            if not isinstance(value, (int, float)):
                                attrs[key] = str(value)
                        except Exception as e:
                            logger.warning(f"属性変換エラー (エッジ {u}-{v}, 属性 {key}): {e}")
                            attrs[key] = f"Value-{key}"
            
            try:
                output = io.BytesIO()
                nx.write_graphml(G, output, infer_numeric_types=True)
                output.seek(0)
                standardized_graphml = output.read().decode("utf-8")
                logger.debug("Successfully exported standardized GraphML")
            except Exception as write_error:
                logger.error(f"GraphML書き込みエラー: {write_error}")
                # 最小限のGraphMLを生成
                minimal_graphml = '<?xml version="1.0" encoding="UTF-8"?>\n'
                minimal_graphml += '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
'
                minimal_graphml += '  <key id="d0" for="node" attr.name="name" attr.type="string"/>\n'
                minimal_graphml += '  <key id="d1" for="node" attr.name="size" attr.type="string"/>\n'
                minimal_graphml += '  <key id="d2" for="node" attr.name="color" attr.type="string"/>\n'
                minimal_graphml += '  <key id="d3" for="node" attr.name="description" attr.type="string"/>\n'
                minimal_graphml += '  <key id="d4" for="node" attr.name="x" attr.type="double"/>\n'
                minimal_graphml += '  <key id="d5" for="node" attr.name="y" attr.type="double"/>\n'
                minimal_graphml += '  <graph edgedefault="undirected">
'
                
                # ノードを追加
                for node, attrs in G.nodes(data=True):
                    minimal_graphml += f'    <node id="{node}">
'
                    minimal_graphml += f'      <data key="d0">{attrs.get("name", f"Node {node}")}</data>
'
                    minimal_graphml += f'      <data key="d1">{attrs.get("size", "5.0")}</data>
'
                    minimal_graphml += f'      <data key="d2">{attrs.get("color", "#1d4ed8")}</data>
'
                    minimal_graphml += f'      <data key="d3">{attrs.get("description", f"Node {node}")}</data>
'
                    minimal_graphml += f'      <data key="d4">{attrs.get("x", "0.0")}</data>
'
                    minimal_graphml += f'      <data key="d5">{attrs.get("y", "0.0")}</data>
'
                    minimal_graphml += '    </node>
'
                
                # エッジを追加
                for u, v, attrs in G.edges(data=True):
                    minimal_graphml += f'    <edge source="{u}" target="{v}"/>\n'
                
                minimal_graphml += '  </graph>
'
                minimal_graphml += '</graphml>'
                
                standardized_graphml = minimal_graphml
                logger.debug("Generated minimal GraphML as fallback")
            
            # <key>要素が存在しない場合は追加
            if "<key " not in standardized_graphml:
                logger.debug("No <key> elements found, adding them")
                try:
                    # <graphml>タグの後に<key>要素を挿入
                    parts = standardized_graphml.split("<graphml ", 1)
                    if len(parts) == 2:
                        # <graphml>タグの閉じ括弧を見つける
                        graphml_tag_parts = parts[1].split(">", 1)
                        if len(graphml_tag_parts) == 2:
                            key_str = ">\n  " + "\n  ".join(key_elements) + "\n  "
                            standardized_graphml = parts[0] + "<graphml " + graphml_tag_parts[0] + key_str + graphml_tag_parts[1]
                        else:
                            # 通常のケース
                            key_str = "\n  " + "\n  ".join(key_elements) + "\n  "
                            standardized_graphml = parts[0] + "<graphml " + parts[1].replace("<graph ", key_str + "<graph ", 1)
                    else:
                        logger.warning("Could not find <graphml> tag for inserting <key> elements")
                        # <graphml>タグが見つからない場合は、最初に<key>要素を追加
                        if standardized_graphml.strip().startswith("<?xml"):
                            xml_parts = standardized_graphml.split("?>", 1)
                            if len(xml_parts) == 2:
                                key_str = "?>\n<graphml>\n  " + "\n  ".join(key_elements) + "\n  "
                                standardized_graphml = xml_parts[0] + key_str + xml_parts[1]
                        else:
                            # XMLヘッダーもない場合は、最初から追加
                            key_str = '<?xml version="1.0" encoding="UTF-8"?>\n<graphml>\n  ' + "\n  ".join(key_elements) + "\n  "
                            standardized_graphml = key_str + standardized_graphml
                except Exception as key_error:
                    logger.error(f"<key>要素の追加中にエラーが発生しました: {key_error}")
                    # エラーが発生した場合でも処理を続行
            
            # エクスポート後の内容をデバッグログに出力
            logger.debug(f"Final standardized GraphML (first 500 chars): {standardized_graphml[:500]}...")
        except Exception as export_error:
            logger.error(f"Error exporting GraphML: {export_error}")
            # エラーの詳細をトレースバックとともに記録
            import traceback
            logger.error(f"Export error traceback: {traceback.format_exc()}")
            
            # より詳細なエラーメッセージを提供
            error_msg = str(export_error)
            if "not a string" in error_msg or "must be a string" in error_msg:
                return {
                    "success": False,
                    "error": f"属性値の型変換に失敗しました。すべての属性値は文字列である必要があります: {error_msg}"
                }
            else:
                return {
                    "success": False,
                    "error": f"標準GraphMLへのエクスポートに失敗しました: {error_msg}"
                }
        
        return {
            "success": True,
            "graph": G,
            "graphml_content": standardized_graphml
        }
    except Exception as e:
        logger.error(f"Error converting GraphML: {e}")
        # エラーの詳細をトレースバックとともに記録
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": f"Error converting GraphML: {str(e)}"
        }

def export_network_as_graphml(G, positions=None, visual_properties=None):
    """
    ネットワークをGraphML形式でエクスポートする
    
    Args:
        G (nx.Graph): NetworkXグラフ
        positions (list, optional): ノードの位置情報
        visual_properties (dict, optional): ビジュアルプロパティ
        
    Returns:
        dict: 処理結果を含む辞書
    """
    try:
        # Create a copy of the graph to avoid modifying the original
        export_G = G.copy()
        
        # Add standard node attributes (name, color, size, description) if not present
        for node in export_G.nodes():
            node_str = str(node)
            
            # Set default attributes if not present
            if 'name' not in export_G.nodes[node]:
                export_G.nodes[node]['name'] = node_str
                
            if 'size' not in export_G.nodes[node]:
                export_G.nodes[node]['size'] = "5.0"  # Default size
                
            if 'color' not in export_G.nodes[node]:
                export_G.nodes[node]['color'] = "#1d4ed8"  # Default color
                
            if 'description' not in export_G.nodes[node]:
                export_G.nodes[node]['description'] = f"Node {node_str}"
        
        # Add positions if provided
        if positions:
            pos_dict = {}
            for node_pos in positions:
                node_id = node_pos["id"]
                if node_id.isdigit():
                    try:
                        node_id = int(node_id)
                    except:
                        pass
                
                if node_id in export_G.nodes():
                    # Add position attributes
                    export_G.nodes[node_id]['x'] = str(node_pos.get('x', 0.0))
                    export_G.nodes[node_id]['y'] = str(node_pos.get('y', 0.0))
                    
                    # Add other visual attributes if present
                    if 'size' in node_pos:
                        export_G.nodes[node_id]['size'] = str(node_pos['size'])
                    if 'color' in node_pos:
                        export_G.nodes[node_id]['color'] = node_pos['color']
                    if 'label' in node_pos:
                        export_G.nodes[node_id]['name'] = node_pos['label']
        
        # Add global visual properties if provided
        if visual_properties:
            # Add graph-level attributes
            export_G.graph['node_default_size'] = str(visual_properties.get('node_size', 5))
            export_G.graph['node_default_color'] = visual_properties.get('node_color', '#1d4ed8')
            export_G.graph['edge_default_width'] = str(visual_properties.get('edge_width', 1))
            export_G.graph['edge_default_color'] = visual_properties.get('edge_color', '#94a3b8')
        
        # Export to GraphML
        output = io.BytesIO()
        nx.write_graphml(export_G, output)
        output.seek(0)
        graphml_content = output.read().decode("utf-8")
        
        return {
            "success": True,
            "format": "graphml",
            "content": graphml_content
        }
    except Exception as e:
        logger.error(f"Error exporting network as GraphML: {e}")
        return {
            "success": False,
            "error": f"Error exporting network as GraphML: {str(e)}"
        }

def get_network_info(G):
    """
    ネットワークの基本情報を取得する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ネットワーク情報
    """
    try:
        # 基本的なネットワーク指標を計算
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()
        density = nx.density(G)
        
        # 連結成分の計算
        is_connected = nx.is_connected(G)
        num_components = nx.number_connected_components(G) if not is_connected else 1
        
        # 次数の計算
        degrees = [d for _, d in G.degree()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0
        
        # クラスタリング係数の計算
        clustering = nx.average_clustering(G)
        
        return {
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "density": density,
            "is_connected": is_connected,
            "num_components": num_components,
            "avg_degree": avg_degree,
            "clustering_coefficient": clustering
        }
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return {
            "error": f"Error getting network info: {str(e)}"
        }


def calculate_centrality(G, centrality_type="degree", **kwargs):
    """
    指定された中心性指標を計算する

    Args:
        G (nx.Graph): NetworkXグラフ
        centrality_type (str): 計算する中心性の種類
            (degree, closeness, betweenness, eigenvector, pagerank)
        **kwargs: 各中心性計算関数に渡す追加の引数

    Returns:
        dict: {node_id: centrality_value} の形式の辞書
    """
    try:
        centrality_calculators = {
            "degree": nx.degree_centrality,
            "closeness": nx.closeness_centrality,
            "betweenness": nx.betweenness_centrality,
            "eigenvector": nx.eigenvector_centrality_numpy,
            "pagerank": nx.pagerank
        }

        if centrality_type not in centrality_calculators:
            raise ValueError(f"Unsupported centrality type: {centrality_type}")

        # 固有ベクトル中心性の場合、max_iterのデフォルト値を設定
        if centrality_type == "eigenvector":
            kwargs.setdefault("max_iter", 1000)

        # 中心性を計算
        centrality = centrality_calculators[centrality_type](G, **kwargs)
        
        # 結果を標準化
        max_value = max(centrality.values()) if centrality else 1.0
        if max_value > 0:
            # 0で除算しないようにチェック
            centrality = {str(k): v / max_value for k, v in centrality.items()}
        else:
            centrality = {str(k): 0 for k, v in centrality.items()}

        return {
            "success": True,
            "centrality_type": centrality_type,
            "centrality": centrality
        }
    except Exception as e:
        logger.error(f"Error calculating {centrality_type} centrality: {e}")
        # エラー発生時にトレースバックをログに出力
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Error calculating {centrality_type} centrality: {str(e)}"
        }
