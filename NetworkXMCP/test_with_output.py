"""
出力を伴うテストスクリプト
====================

テスト結果をファイルに書き出す
"""

import sys
import os

# 結果を記録するためのファイル
output_file = "test_results.txt"

def write_log(message):
    """ログをファイルに書き出す"""
    with open(output_file, "a") as f:
        f.write(message + "\n")
    print(message)

# ファイルを初期化
with open(output_file, "w") as f:
    f.write("テスト開始\n")

write_log("Python version: " + sys.version)
write_log("Current working directory: " + os.getcwd())
write_log("sys.path: " + str(sys.path))

try:
    write_log("\nテスト1: グラフ作成モジュールの読み込み")
    from tools.graph_creation import create_random_network
    write_log("✓ create_random_network 関数が正常にインポートされました")
    
    write_log("\nテスト2: GraphMLパーサーモジュールの読み込み")
    from tools.graphml_parser import parse_graphml_string, fix_graphml_structure
    write_log("✓ parse_graphml_string 関数が正常にインポートされました")
    write_log("✓ fix_graphml_structure 関数が正常にインポートされました")
    
    write_log("\nテスト3: GraphML変換モジュールの読み込み")
    from tools.graphml_converter import convert_to_standard_graphml, export_network_as_graphml
    write_log("✓ convert_to_standard_graphml 関数が正常にインポートされました")
    write_log("✓ export_network_as_graphml 関数が正常にインポートされました")
    
    write_log("\nテスト4: ネットワーク分析モジュールの読み込み")
    from tools.network_analysis import get_network_info, calculate_centrality
    write_log("✓ get_network_info 関数が正常にインポートされました")
    write_log("✓ calculate_centrality 関数が正常にインポートされました")
    
    write_log("\nテスト5: __init__.py 経由の読み込み")
    from tools import (
        create_random_network,
        parse_graphml_string,
        fix_graphml_structure,
        convert_to_standard_graphml,
        export_network_as_graphml,
        get_network_info,
        calculate_centrality
    )
    write_log("✓ __init__.py 経由で全ての関数が正常にインポートされました")
    
    # 実際の機能テスト
    write_log("\nテスト6: ランダムネットワーク生成")
    G, nodes, edges = create_random_network(num_nodes=5, edge_probability=0.3)
    write_log(f"✓ ランダムネットワーク生成: ノード数={len(nodes)}, エッジ数={len(edges)}")
    
    write_log("\nテスト7: ネットワーク情報取得")
    info = get_network_info(G)
    write_log(f"✓ ネットワーク情報取得: {info}")
    
    write_log("\nテスト8: 中心性計算")
    result = calculate_centrality(G, centrality_type="degree")
    if result["success"]:
        write_log("✓ 次数中心性計算成功")
    
    write_log("\nテスト9: GraphMLエクスポート")
    export_result = export_network_as_graphml(G)
    if export_result["success"]:
        write_log("✓ GraphMLエクスポート成功")
    
    write_log("\nすべてのテストが成功しました！")
    
except Exception as e:
    write_log(f"エラー: {e}")
    import traceback
    write_log(traceback.format_exc())

write_log("\nテスト結果は " + output_file + " に保存されました")
