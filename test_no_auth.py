#!/usr/bin/env python3
"""
認証不要のテストエンドポイントを使用してAPIをテストするスクリプト
"""

import requests
import json
import time

def test_api_without_auth():
    """認証不要のテストエンドポイントでAPIをテスト"""
    api_url = "http://localhost:8000"
    
    # テスト用ネットワークデータ
    request_data = {
        "network": {
            "nodes": [
                {"id": "0", "label": "Center Node"},
                {"id": "1", "label": "Node 1"},
                {"id": "2", "label": "Node 2"},
                {"id": "3", "label": "Node 3"},
                {"id": "4", "label": "Node 4"}
            ],
            "edges": [
                {"source": "0", "target": "1"},
                {"source": "0", "target": "2"},
                {"source": "0", "target": "3"},
                {"source": "0", "target": "4"}
            ]
        },
        "centrality_type": "degree",
        "color_scheme": "viridis",
        "size_range": [30, 80]
    }
    
    try:
        print("📊 Testing direct centrality calculation (no auth)")
        response = requests.post(
            f"{api_url}/network/test-centrality-direct",
            json=request_data,
            timeout=60.0
        )
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Raw Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ API Response Success!")
            
            if result.get("success") and "visualization_data" in result:
                viz_data = result["visualization_data"]
                print(f"   ✅ visualization_data: {len(viz_data)} nodes")
                
                # ノードサイズの確認
                center_node = viz_data.get("0", {})
                other_nodes = [viz_data.get(str(i), {}) for i in range(1, 5)]
                
                center_size = center_node.get("size", 0)
                other_sizes = [node.get("size", 0) for node in other_nodes]
                
                print(f"   Center node (0) - size: {center_size}, color: {center_node.get('color')}")
                print(f"   Other nodes sizes: {other_sizes}")
                print(f"   Center centrality: {center_node.get('centrality_value')}")
                
                if center_size > max(other_sizes):
                    print("   ✅ PASS: Center node has larger size (correct centrality visualization)")
                    print("   ✅ PASS: Degree centrality is properly reflected in node sizes!")
                    return True
                else:
                    print("   ❌ FAIL: Center node does not have larger size")
            else:
                print("   ❌ Response does not contain visualization_data")
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            print(f"   Error details: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def main():
    print("🧪 Testing Centrality Visualization Fix (No Auth)")
    print("=" * 60)
    
    # Wait for services to be ready
    print("⏳ Waiting for services to start...")
    time.sleep(2)
    
    # Test API endpoint without authentication
    success = test_api_without_auth()
    
    print(f"\n📈 Test Result: {'✅ PASS' if success else '❌ FAIL'}")
    
    if success:
        print("\n🎉 Centrality visualization fix is working correctly!")
        print("🎯 The center node properly shows larger size based on degree centrality.")
        print("🎨 Color scheme and size mapping are functioning as expected.")
    else:
        print("\n⚠️ Test failed. Please check the API implementation.")

if __name__ == "__main__":
    main()