
import math
import sys
import os

# Add relevant paths
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "networkx-api"))

from app.logic.common_utils import calculate_smart_node_size

def test_size(n):
    res = calculate_smart_node_size(n)
    print(f"N={n}: {res}")

print("--- Testing calculate_smart_node_size ---")
test_size(10)
test_size(50)
test_size(100)
test_size(1000)
test_size(14400)
test_size(20000)

print("\n--- Inspecting Strings in Visualization Schema ---")
try:
    with open("networkx-api/app/schemas/visualization.py", "r") as f:
        content = f.read()
        if 'description="Min node radius. Prefer leaving as None' in content:
            print("Schema updated correctly.")
        else:
            print("Schema NOT updated.")
            # Print the relevant section
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "class NodeSizeConfig" in line:
                    print("\n".join(lines[i:i+15]))
except Exception as e:
    print(f"Error reading schema: {e}")
