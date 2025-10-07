"""
GraphML解析モジュール
===================

GraphML形式のデータを解析・修正するためのモジュール
"""

import networkx as nx
import logging
import io
import re
from typing import Dict, Any, Optional

# ロギングの設定
logger = logging.getLogger("networkx_mcp.tools.graphml_parser")

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
                r"(<graph>)",
                r'\1 edgedefault="undirected" ',
                graphml_content,
                count=1
            )
        
        # 不正なXML文字を削除
        # XMLの不正な文字を削除するパターン
        # XMLで使用できない文字のパターン
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
