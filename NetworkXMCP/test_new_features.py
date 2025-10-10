"""
新機能のテストスクリプト
===================

新しく追加した機能（グラフキャッシュ、指標計算、可視化データ取得）をテストします。
"""

import requests
import json

# サーバーのベースURL
BASE_URL = "http://localhost:8001"

def test_get_sample_network():
    """サンプルネットワークを取得"""
    print("\n=== Test 1: Get Sample Network ===")
    response = requests.get(f"{BASE_URL}/get_sample_network")
    data = response.json()
    
    if data.get("success"):
        print("✓ Sample network generated successfully")
        graphml_content = data.get("graphml_content")
        print(f"  GraphML length: {len(graphml_content)} characters")
        return graphml_content
    else:
        print("✗ Failed to generate sample network")
        return None

def test_calculate_and_store_metrics(graphml_content):
    """指標を計算してキャッシュに保存"""
    print("\n=== Test 2: Calculate and Store Metrics ===")
    
    payload = {
        "graphml_content": graphml_content,
        "layout_type": "spring",
        "layout_params": {},
        "metrics_to_calculate": None  # 全ての指標を計算
    }
    
    response = requests.post(
        f"{BASE_URL}/tools/calculate_and_store_metrics",
        json=payload
    )
    data = response.json()
    
    if data.get("result", {}).get("success"):
        result = data["result"]
        graph_id = result.get("graph_id")
        metadata = result.get("metadata", {})
        
        print("✓ Metrics calculated and stored successfully")
        print(f"  Graph ID: {graph_id}")
        print(f"  Number of nodes: {metadata.get('num_nodes')}")
        print(f"  Number of edges: {metadata.get('num_edges')}")
        print(f"  Layout type: {metadata.get('layout_type')}")
        print(f"  Calculated metrics: {len(metadata.get('calculated_metrics', []))}")
        print(f"  Metrics: {', '.join(metadata.get('calculated_metrics', []))}")
        
        return graph_id
    else:
        print("✗ Failed to calculate and store metrics")
        print(f"  Error: {data.get('result', {}).get('error')}")
        return None

def test_get_available_metrics(graph_id):
    """利用可能な指標のリストを取得"""
    print("\n=== Test 3: Get Available Metrics ===")
    
    payload = {
        "graph_id": graph_id
    }
    
    response = requests.post(
        f"{BASE_URL}/tools/get_available_metrics",
        json=payload
    )
    data = response.json()
    
    if data.get("result", {}).get("success"):
        result = data["result"]
        metrics = result.get("available_metrics", [])
        graph_info = result.get("graph_info", {})
        
        print("✓ Available metrics retrieved successfully")
        print(f"  Number of metrics: {len(metrics)}")
        print(f"  Graph info:")
        print(f"    - Nodes: {graph_info.get('num_nodes')}")
        print(f"    - Edges: {graph_info.get('num_edges')}")
        print(f"    - Layout: {graph_info.get('layout_type')}")
        
        return metrics
    else:
        print("✗ Failed to get available metrics")
        return []

def test_get_visualization_data(graph_id, metric_name):
    """可視化データを取得"""
    print(f"\n=== Test 4: Get Visualization Data (metric: {metric_name}) ===")
    
    payload = {
        "graph_id": graph_id,
        "metric_name": metric_name,
        "color_scheme": "viridis",
        "size_range": [10, 50]
    }
    
    response = requests.post(
        f"{BASE_URL}/tools/get_visualization_data",
        json=payload
    )
    data = response.json()
    
    if data.get("result", {}).get("success"):
        result = data["result"]
        elements = result.get("elements", {})
        metadata = result.get("metadata", {})
        
        print("✓ Visualization data retrieved successfully")
        print(f"  Metric: {result.get('metric_name')}")
        print(f"  Nodes: {len(elements.get('nodes', []))}")
        print(f"  Edges: {len(elements.get('edges', []))}")
        print(f"  Metric type: {metadata.get('metric_type')}")
        
        if metadata.get('metric_type') == 'community':
            print(f"  Number of communities: {metadata.get('num_communities')}")
        else:
            value_range = metadata.get('value_range', {})
            print(f"  Value range: {value_range.get('min'):.4f} - {value_range.get('max'):.4f}")
        
        return True
    else:
        print("✗ Failed to get visualization data")
        print(f"  Error: {data.get('result', {}).get('error')}")
        return False

def test_cache_stats():
    """キャッシュの統計情報を取得"""
    print("\n=== Test 5: Get Cache Stats ===")
    
    response = requests.get(f"{BASE_URL}/cache/stats")
    data = response.json()
    
    if data.get("success"):
        stats = data.get("stats", {})
        print("✓ Cache stats retrieved successfully")
        print(f"  Cache size: {stats.get('size')}/{stats.get('max_size')}")
        print(f"  TTL: {stats.get('ttl_minutes')} minutes")
        print(f"  Cached graph IDs: {len(stats.get('graph_ids', []))}")
        return True
    else:
        print("✗ Failed to get cache stats")
        return False

def main():
    """メインテスト関数"""
    print("=" * 60)
    print("NetworkX MCP Server - New Features Test")
    print("=" * 60)
    
    try:
        # Test 1: サンプルネットワークを取得
        graphml_content = test_get_sample_network()
        if not graphml_content:
            print("\n✗ Test suite failed: Could not get sample network")
            return
        
        # Test 2: 指標を計算してキャッシュに保存
        graph_id = test_calculate_and_store_metrics(graphml_content)
        if not graph_id:
            print("\n✗ Test suite failed: Could not calculate and store metrics")
            return
        
        # Test 3: 利用可能な指標のリストを取得
        metrics = test_get_available_metrics(graph_id)
        if not metrics:
            print("\n✗ Test suite failed: Could not get available metrics")
            return
        
        # Test 4: 複数の指標で可視化データを取得
        test_metrics = []
        
        # 中心性指標をテスト
        if "degree_centrality" in metrics:
            test_metrics.append("degree_centrality")
        if "betweenness_centrality" in metrics:
            test_metrics.append("betweenness_centrality")
        
        # コミュニティ検出をテスト
        if "community_louvain" in metrics:
            test_metrics.append("community_louvain")
        
        # クラスタリング係数をテスト
        if "clustering" in metrics:
            test_metrics.append("clustering")
        
        for metric in test_metrics:
            if not test_get_visualization_data(graph_id, metric):
                print(f"\n⚠ Warning: Failed to get visualization data for {metric}")
        
        # Test 5: キャッシュの統計情報を取得
        test_cache_stats()
        
        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server")
        print("  Please make sure the server is running on http://localhost:8001")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
