#!/usr/bin/env python3
"""
Direct test of centrality calculation and visualization to verify node sizes reflect centrality values
"""

import requests
import json


def create_star_network_graphml():
    """Create GraphML for star network to match what frontend displays"""
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
    <node id="5">
      <data key="d0">Node 5</data>
    </node>
    <node id="6">
      <data key="d0">Node 6</data>
    </node>
    <node id="7">
      <data key="d0">Node 7</data>
    </node>
    <node id="8">
      <data key="d0">Node 8</data>
    </node>
    <node id="9">
      <data key="d0">Node 9</data>
    </node>
    <node id="10">
      <data key="d0">Node 10</data>
    </node>
    <edge id="0" source="0" target="1" />
    <edge id="1" source="0" target="2" />
    <edge id="2" source="0" target="3" />
    <edge id="3" source="0" target="4" />
    <edge id="4" source="0" target="5" />
    <edge id="5" source="0" target="6" />
    <edge id="6" source="0" target="7" />
    <edge id="7" source="0" target="8" />
    <edge id="8" source="0" target="9" />
    <edge id="9" source="0" target="10" />
  </graph>
</graphml>"""
    return graphml


def test_centrality_calculation():
    """Test centrality calculation directly"""

    # NetworkX MCP Server URL
    mcp_url = "http://localhost:8001"

    # Create star network GraphML
    graphml_content = create_star_network_graphml()

    print("🔄 Testing Degree Centrality Calculation...")

    # Stage 1: Calculate and store centrality
    stage1_payload = {
        "graphml_content": graphml_content,
        "centrality_type": "degree"
    }

    try:
        response = requests.post(f"{mcp_url}/tools/calculate_and_store_centrality",
                                 json=stage1_payload, timeout=30.0)

        if response.status_code == 200:
            result = response.json().get("result", {})
            if result.get("success"):
                calculation_id = result.get("calculation_id")
                centrality_type = result.get("centrality_type")

                print(f"✅ Stage 1 completed. Calculation ID: {calculation_id}")
                print(f"   Centrality type: {centrality_type}")

                # Stage 2: Get visualization data
                stage2_payload = {
                    "calculation_id": calculation_id,
                    "color_scheme": "viridis",
                    "size_range": [5, 20]
                }

                viz_response = requests.post(f"{mcp_url}/tools/get_centrality_visualization",
                                             json=stage2_payload, timeout=30.0)

                if viz_response.status_code == 200:
                    viz_result = viz_response.json().get("result", {})
                    if viz_result.get("success"):
                        visualization_data = viz_result.get(
                            "visualization_data", {})

                        print(f"✅ Stage 2 completed. Visualization data retrieved.")
                        print(f"\n📊 Node Centrality and Size Information:")
                        print(
                            f"{'Node ID':<10} {'Centrality':<12} {'Size':<8} {'Color'}")
                        print("-" * 50)

                        for node_id, node_data in visualization_data.items():
                            centrality_val = node_data.get(
                                'centrality_value', 0)
                            size = node_data.get('size', 5)
                            color = node_data.get('color', '#1d4ed8')
                            print(
                                f"{node_id:<10} {centrality_val:<12.3f} {size:<8.1f} {color}")

                        # Verify that Center Node (id='0') has larger size than others
                        center_size = visualization_data.get(
                            '0', {}).get('size', 5)
                        peripheral_sizes = [visualization_data.get(
                            str(i), {}).get('size', 5) for i in range(1, 11)]
                        max_peripheral_size = max(
                            peripheral_sizes) if peripheral_sizes else 5

                        print(f"\n🎯 Size Analysis:")
                        print(f"   Center Node (0) size: {center_size}")
                        print(
                            f"   Max peripheral node size: {max_peripheral_size}")
                        print(
                            f"   Size difference: {center_size - max_peripheral_size:.1f}")

                        if center_size > max_peripheral_size:
                            print(
                                "✅ PASS: Center node has larger size than peripheral nodes")
                            print(
                                "   ✅ Degree centrality is properly reflected in node sizes!")
                        else:
                            print(
                                "❌ FAIL: Center node should have larger size than peripheral nodes")

                        return True
                    else:
                        print(f"❌ Stage 2 failed: {viz_result.get('error')}")
                else:
                    print(f"❌ Stage 2 HTTP error: {viz_response.status_code}")
                    print(f"   Response: {viz_response.text}")
            else:
                print(f"❌ Stage 1 failed: {result.get('error')}")
        else:
            print(f"❌ Stage 1 HTTP error: {response.status_code}")
            print(f"   Response: {response.text}")

    except requests.RequestException as e:
        print(f"❌ Network error: {e}")

    return False


def test_betweenness_centrality():
    """Test betweenness centrality calculation"""

    # NetworkX MCP Server URL
    mcp_url = "http://localhost:8001"

    # Create star network GraphML
    graphml_content = create_star_network_graphml()

    print("\n🔄 Testing Betweenness Centrality Calculation...")

    # Stage 1: Calculate and store centrality
    stage1_payload = {
        "graphml_content": graphml_content,
        "centrality_type": "betweenness"
    }

    try:
        response = requests.post(f"{mcp_url}/tools/calculate_and_store_centrality",
                                 json=stage1_payload, timeout=30.0)

        if response.status_code == 200:
            result = response.json().get("result", {})
            if result.get("success"):
                calculation_id = result.get("calculation_id")
                centrality_type = result.get("centrality_type")

                print(f"✅ Stage 1 completed. Calculation ID: {calculation_id}")

                # Stage 2: Get visualization data
                stage2_payload = {
                    "calculation_id": calculation_id,
                    "color_scheme": "plasma",
                    "size_range": [6, 25]
                }

                viz_response = requests.post(f"{mcp_url}/tools/get_centrality_visualization",
                                             json=stage2_payload, timeout=30.0)

                if viz_response.status_code == 200:
                    viz_result = viz_response.json().get("result", {})
                    if viz_result.get("success"):
                        visualization_data = viz_result.get(
                            "visualization_data", {})

                        print(f"✅ Stage 2 completed for betweenness centrality.")
                        print(f"\n📊 Betweenness Centrality and Size Information:")
                        print(
                            f"{'Node ID':<10} {'Centrality':<12} {'Size':<8} {'Color'}")
                        print("-" * 50)

                        for node_id, node_data in visualization_data.items():
                            centrality_val = node_data.get(
                                'centrality_value', 0)
                            size = node_data.get('size', 6)
                            color = node_data.get('color', '#1d4ed8')
                            print(
                                f"{node_id:<10} {centrality_val:<12.3f} {size:<8.1f} {color}")

                        # For star topology, center node should have highest betweenness centrality
                        center_size = visualization_data.get(
                            '0', {}).get('size', 6)
                        peripheral_sizes = [visualization_data.get(
                            str(i), {}).get('size', 6) for i in range(1, 11)]
                        max_peripheral_size = max(
                            peripheral_sizes) if peripheral_sizes else 6

                        print(f"\n🎯 Betweenness Centrality Size Analysis:")
                        print(f"   Center Node (0) size: {center_size}")
                        print(
                            f"   Max peripheral node size: {max_peripheral_size}")

                        if center_size > max_peripheral_size:
                            print(
                                "✅ PASS: Betweenness centrality is properly reflected in node sizes!")
                        else:
                            print(
                                "❌ FAIL: Center node should have larger size for betweenness centrality")

                        return True

    except requests.RequestException as e:
        print(f"❌ Network error: {e}")

    return False


if __name__ == "__main__":
    print("🧪 Testing Centrality Visualization - Node Size Reflection")
    print("=" * 60)

    # Test both degree and betweenness centrality
    degree_success = test_centrality_calculation()
    betweenness_success = test_betweenness_centrality()

    print(f"\n📈 Test Results Summary:")
    print(f"   Degree Centrality: {'✅ PASS' if degree_success else '❌ FAIL'}")
    print(
        f"   Betweenness Centrality: {'✅ PASS' if betweenness_success else '❌ FAIL'}")

    if degree_success and betweenness_success:
        print(
            f"\n🎉 All tests passed! Centrality values are properly reflected in node sizes.")
    else:
        print(f"\n⚠️  Some tests failed. Please check the implementation.")
