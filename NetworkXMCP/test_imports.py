"""
機能テストスクリプト
================

リファクタリング後の機能テスト
"""

import networkx as nx
import logging
import sys

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# 分割した各モジュールからの関数インポートをテスト
from tools import (
    create_random_network,
    parse_graphml_string,
    fix_graphml_structure,
    convert_to_standard_graphml,
    export_network_as_graphml,
    get_network_info,
    calculate_centrality
)

def test_imports():
    """すべての関数がエクスポートされ、インポート可能であることをテスト"""
    print("すべての関数が正常にインポートされました")
    
    # 関数の存在確認
    functions = [
        create_random_network,
        parse_graphml_string,
        fix_graphml_structure,
        convert_to_standard_graphml,
        export_network_as_graphml,
        get_network_info,
        calculate_centrality
    ]
    
    print(f"インポートされた関数の数: {len(functions)}")
    for i, func in enumerate(functions, 1):
        print(f"{i}. {func.__name__}")
    
    return True

def test_create_random_network():
    """ランダムネットワーク生成機能のテスト"""
    print("\nランダムネットワーク生成のテスト:")
    G, nodes, edges = create_random_network(num_nodes=5, edge_probability=0.3)
    
    print(f"生成されたノード数: {len(nodes)}")
    print(f"生成されたエッジ数: {len(edges)}")
    
    # ネットワーク情報の取得テスト
    info = get_network_info(G)
    print(f"ネットワーク情報: {info}")
    
    return G, nodes, edges

def main():
    """メイン関数"""
    print("NetworkXMCP ツールモジュールテスト\n" + "="*30)
    
    # インポートテスト
    test_imports()
    
    # ランダムネットワーク生成と分析のテスト
    G, nodes, edges = test_create_random_network()
    
    # 中心性計算のテスト
    print("\n中心性計算のテスト:")
    result = calculate_centrality(G, centrality_type="degree")
    if result["success"]:
        print("次数中心性の計算に成功しました")
        print(f"計算された中心性: {result['centrality']}")
    
    # GraphMLエクスポートのテスト
    print("\nGraphMLエクスポートのテスト:")
    export_result = export_network_as_graphml(G)
    if export_result["success"]:
        print("GraphMLエクスポートに成功しました")
        graphml_content = export_result["content"]
        print(f"GraphML内容の長さ: {len(graphml_content)} 文字")
    
    print("\nすべてのテストが完了しました")

if __name__ == "__main__":
    main()
