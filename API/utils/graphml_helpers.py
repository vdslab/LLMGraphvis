"""
モジュール名: graphml_helpers.py
責務: GraphML処理ヘルパー（生成・パース）
依存: networkx, io
依存先: API層（routers/chat.py, services/*）

主要な関数:
- create_empty_graphml: 空のGraphMLを生成
- parse_graphml: GraphML文字列をnx.Graphにパース

変更時の注意:
- GraphMLのエンコード/デコードはUTF-8で統一
- 将来Directed/Attributed Graphへ拡張する場合はI/O仕様に注意
"""

import io
import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

def create_empty_graphml() -> str:
    """
    空のGraphMLを生成

    Args:
        なし

    Returns:
        UTF-8エンコードの空GraphML文字列
    """
    try:
        G = nx.Graph()
        output = io.BytesIO()
        nx.write_graphml(G, output)
        return output.getvalue().decode("utf-8")
    except Exception as e:
        logger.error(f"Error creating empty GraphML: {type(e).__name__}: {e}", exc_info=True)
        raise

def parse_graphml(graphml_str: str) -> nx.Graph:
    """
    GraphML文字列をパースしてnetworkx Graphを返す

    Args:
        graphml_str: GraphML形式の文字列

    Returns:
        networkx.Graph オブジェクト

    Raises:
        ValueError: graphml_str が空の場合
    """
    if not graphml_str:
        raise ValueError("graphml_str must not be empty")
    try:
        return nx.read_graphml(io.StringIO(graphml_str))
    except Exception as e:
        logger.error(f"Error parsing GraphML: {type(e).__name__}: {e}", exc_info=True)
        raise