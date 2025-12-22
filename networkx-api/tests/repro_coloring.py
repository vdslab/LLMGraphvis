import os
import sys

# Add the parent directory to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.logic.style_service import StyleService


def test_repro_autofill_prevented_by_default_color():
    print("Testing if default_color prevents autofill...")

    # Configuration simulating user request: "Color by nationality"
    # LLM might provide a default_color but empty color_map
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "nationality",
        "default_color": "#CCCCCC",  # This triggers the bug
        "color_map": {},
    }

    # Mock data
    # 5 nodes with nationalities
    attr_map = {"nationality": 1}
    values_map = {
        101: {1: "Japan"},
        102: {1: "USA"},
        103: {1: "France"},
        104: {1: "Japan"},
        105: {1: "USA"},
    }

    # Expected: "Japan", "USA", "France" should have colors in the map.

    result_map = StyleService.prepare_categorical_map(config, attr_map, values_map)

    print(f"Result Map: {result_map}")

    if "Japan" not in result_map:
        print("FAIL: 'Japan' not in map (Autofill prevented)")
        exit(1)

    if "USA" not in result_map:
        print("FAIL: 'USA' not in map")
        exit(1)

    print("SUCCESS: Autofill worked (Bug not present or fixed)")


if __name__ == "__main__":
    test_repro_autofill_prevented_by_default_color()
