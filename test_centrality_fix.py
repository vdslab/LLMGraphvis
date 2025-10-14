#!/usr/bin/env python3
"""
中心性可視化の修正をテストするスクリプト
"""

import requests
import json
import time

def create_test_graphml():
    """テスト用のスターネットワークGraphMLを作成"""
    graphml = """<?xml version='1.0' encoding='utf-8'?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="label" attr.type="string" />
  <graph id="G" edgedefault="undirected">
    <node id="0">
      <data key="d0">Center Node</data>
    </node>
    <node id="1">
      <data key="d0">Node 1</data>
    </node>
    <node id="2">
      <data key="d0">Node 2</data>
    </node>
    <node id="3">
      <data key="d0">Node 3</data>
    </node>
    <node id="4">
      <data key="d0">Node 4</data>
    </node>
    <edge id="0" source="0" target="1" />
    <edge id="1" source="0" target="2" />
    <edge id="2" source="0" target="3" />
    <edge id="3" source="0" target="4" />
  </graph>
</graphml>"""
    return graphml

def test_networkx_mcp_endpoints():
    """NetworkXMCPサーバーのエンドポイントを直接テスト"""
    mcp_url = "http://localhost:8001"
    graphml_content = create_test_graphml()
    
    print("🔄 Testing NetworkX MCP endpoints directly...")
    
    # Stage 1: Calculate and store centrality
    stage1_payload = {
        "graphml_content": graphml_content,
        "centrality_type": "degree"
    }
    
    try:
        print("📊 Stage 1: Calculate and store centrality")
        response = requests.post(f"{mcp_url}/tools/calculate_and_store_centrality",
                                json=stage1_payload, timeout=30.0)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Raw Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Parsed Response: {json.dumps(result, indent=2)}")
            
            # calculation_idを取得
            if "result" in result and "calculation_id" in result["result"]:
                calculation_id = result["result"]["calculation_id"]
                print(f"   ✅ calculation_id extracted: {calculation_id}")
                
                # Stage 2: Get visualization data
                stage2_payload = {
                    "calculation_id": calculation_id,
                    "color_scheme": "viridis",
                    "size_range": [30, 80]
                }
                
                print("🎨 Stage 2: Get visualization data")
                viz_response = requests.post(f"{mcp_url}/tools/get_centrality_visualization",
                                           json=stage2_payload, timeout=30.0)
                
                print(f"   Status Code: {viz_response.status_code}")
                print(f"   Raw Response: {viz_response.text}")
                
                if viz_response.status_code == 200:
                    viz_result = viz_response.json()
                    print(f"   Parsed Response: {json.dumps(viz_result, indent=2)}")
                    
                    if "result" in viz_result and "visualization_data" in viz_result["result"]:
                        viz_data = viz_result["result"]["visualization_data"]
                        print(f"   ✅ visualization_data extracted: {len(viz_data)} nodes")
                        return True
                    else:
                        print("   ❌ No visualization_data in response")
                else:
                    print(f"   ❌ Stage 2 failed: {viz_response.status_code}")
            else:
                print("   ❌ No calculation_id in response")
        else:
            print(f"   ❌ Stage 1 failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def test_api_endpoint():
    """APIエンドポイントをテスト"""
    api_url = "http://localhost:8000"
    
    print("\n🔄 Testing API endpoint...")
    
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
        print("📊 Testing direct centrality calculation")
        response = requests.post(f"{api_url}/network/calculate-centrality-direct",
                                json=request_data, timeout=60.0)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Raw Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Parsed Response: {json.dumps(result, indent=2)}")
            
            if result.get("success") and "visualization_data" in result:
                viz_data = result["visualization_data"]
                print(f"   ✅ Success! visualization_data: {len(viz_data)} nodes")
                
                # ノードサイズの確認
                center_node = viz_data.get("0", {})
                other_nodes = [viz_data.get(str(i), {}) for i in range(1, 5)]
                
                center_size = center_node.get("size", 0)
                other_sizes = [node.get("size", 0) for node in other_nodes]
                
                print(f"   Center node size: {center_size}")
                print(f"   Other nodes sizes: {other_sizes}")
                
                if center_size > max(other_sizes):
                    print("   ✅ Center node has larger size (correct centrality visualization)")
                    return True
                else:
                    print("   ❌ Center node does not have larger size")
            else:
                print("   ❌ Response does not contain visualization_data")
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def main():
    print("🧪 Testing Centrality Visualization Fix")
    print("=" * 50)
    
    # Wait for services to be ready
    print("⏳ Waiting for services to start...")
    time.sleep(5)
    
    # Test NetworkX MCP endpoints
    mcp_success = test_networkx_mcp_endpoints()
    
    # Test API endpoint
    api_success = test_api_endpoint()
    
    print("\n📈 Test Results:")
    print(f"   NetworkX MCP: {'✅ PASS' if mcp_success else '❌ FAIL'}")
    print(f"   API Endpoint: {'✅ PASS' if api_success else '❌ FAIL'}")
    
    if mcp_success and api_success:
        print("\n🎉 All tests passed! Centrality visualization fix is working.")
    else:
        print("\n⚠️ Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    main()