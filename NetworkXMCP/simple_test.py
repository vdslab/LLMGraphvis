"""
シンプルテストスクリプト
================

リファクタリング後のシンプルな機能テスト
"""

import sys
print("Python version:", sys.version)
print("Current working directory:", sys.path)

try:
    print("\nテスト1: グラフ作成モジュールの読み込み")
    from tools.graph_creation import create_random_network
    print("✓ create_random_network 関数が正常にインポートされました")
    
    print("\nテスト2: GraphMLパーサーモジュールの読み込み")
    from tools.graphml_parser import parse_graphml_string, fix_graphml_structure
    print("✓ parse_graphml_string 関数が正常にインポートされました")
    print("✓ fix_graphml_structure 関数が正常にインポートされました")
    
    print("\nテスト3: GraphML変換モジュールの読み込み")
    from tools.graphml_converter import convert_to_standard_graphml, export_network_as_graphml
    print("✓ convert_to_standard_graphml 関数が正常にインポートされました")
    print("✓ export_network_as_graphml 関数が正常にインポートされました")
    
    print("\nテスト4: ネットワーク分析モジュールの読み込み")
    from tools.network_analysis import get_network_info, calculate_centrality
    print("✓ get_network_info 関数が正常にインポートされました")
    print("✓ calculate_centrality 関数が正常にインポートされました")
    
    print("\nテスト5: __init__.py 経由の読み込み")
    from tools import (
        create_random_network,
        parse_graphml_string,
        fix_graphml_structure,
        convert_to_standard_graphml,
        export_network_as_graphml,
        get_network_info,
        calculate_centrality
    )
    print("✓ __init__.py 経由で全ての関数が正常にインポートされました")
    
    print("\nすべてのインポートテストが成功しました！")
    
except ImportError as e:
    print(f"エラー: {e}")
    import traceback
    traceback.print_exc()
