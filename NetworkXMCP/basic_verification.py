"""
基本検証スクリプト
================

ファイル分割後のNetworkXMCPツールモジュールの基本検証
"""

print("Starting basic verification...")

# スクリプトを生成
verification_script = """
import sys
import os

print("===== NetworkXMCP Tools Module Verification =====")

try:
    print("\\nVerifying imports from individual modules...")
    
    print("1. Importing from graph_creation...")
    from tools.graph_creation import create_random_network
    print("   Success: create_random_network imported")
    
    print("2. Importing from graphml_parser...")
    from tools.graphml_parser import parse_graphml_string, fix_graphml_structure
    print("   Success: parse_graphml_string and fix_graphml_structure imported")
    
    print("3. Importing from graphml_converter...")
    from tools.graphml_converter import convert_to_standard_graphml, export_network_as_graphml
    print("   Success: convert_to_standard_graphml and export_network_as_graphml imported")
    
    print("4. Importing from network_analysis...")
    from tools.network_analysis import get_network_info, calculate_centrality
    print("   Success: get_network_info and calculate_centrality imported")
    
    print("\\nVerifying imports from __init__.py...")
    from tools import (
        create_random_network,
        parse_graphml_string,
        fix_graphml_structure,
        convert_to_standard_graphml,
        export_network_as_graphml,
        get_network_info,
        calculate_centrality
    )
    print("   Success: All functions imported from tools package")
    
    print("\\nTesting create_random_network...")
    G, nodes, edges = create_random_network(num_nodes=5, edge_probability=0.3)
    print(f"   Created network with {len(nodes)} nodes and {len(edges)} edges")
    
    print("\\nTesting get_network_info...")
    info = get_network_info(G)
    print(f"   Network info: {info}")
    
    print("\\nVerification complete! All tests passed.")
    
except Exception as e:
    print(f"\\nError: {e}")
    import traceback
    print(traceback.format_exc())
"""

# 検証スクリプトを一時ファイルに書き出す
temp_script = "temp_verification.py"
with open(temp_script, "w") as f:
    f.write(verification_script)

print(f"Created verification script: {temp_script}")
print("Please execute the following command to run the verification:")
print(f"python {temp_script}")
print("\nIf all tests pass, it confirms that the module splitting was successful.")
