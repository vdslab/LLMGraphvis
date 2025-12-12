from app.mcp_server import mcp
from app.schemas.visualization import NodeColorConfig, NodeSizeConfig, VisualizationRequest
from app.schemas.filter import AttributeCondition
import asyncio
import json

async def test_generate_visualization_validation():
    print("\n--- Testing generate_visualization Validation ---")
    
    # Test Case 1: Valid Config
    print("Test 1: Valid Config")
    valid_color_config = NodeColorConfig(
        scale_type="CATEGORICAL",
        attribute="nationality", 
        color_map={"Japan": "#FF0000"}
    )
    # We can't easily call the tool directly via mcp.call_tool without running the server, 
    # but we can try to instantiate the model to verify Pydantic rules.
    try:
        print(f"Valid Model: {valid_color_config}")
    except Exception as e:
        print(f"FAILED: Valid config raised error: {e}")

    # Test Case 2: Invalid Config (Missing required field)
    print("Test 2: Invalid Config (Missing attribute)")
    try:
        NodeColorConfig(scale_type="LINEAR")
        print("FAILED: Invalid config should have raised ValidationError")
    except Exception as e:
        print(f"PASSED: Caught expected error: {e}")

async def test_filter_validation():
    print("\n--- Testing create_subgraph_by_attribute_filter Validation ---")
    
    # Test Case 3: Valid Filter
    print("Test 3: Valid Filter")
    valid_condition = AttributeCondition(
        attribute_name="age",
        ranges=[{"min": 10, "max": 20}]
    )
    print(f"Valid Condition: {valid_condition}")

    # Test Case 4: Invalid Filter (Wrong type)
    print("Test 4: Invalid Filter (Wrong range type)")
    try:
        AttributeCondition(attribute_name="age", ranges=["invalid"])
        print("FAILED: Invalid filter should have raised ValidationError")
    except Exception as e:
         print(f"PASSED: Caught expected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_generate_visualization_validation())
    asyncio.run(test_filter_validation())
