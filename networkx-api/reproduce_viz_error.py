
from app.logic.style_service import StyleService
import traceback

def test_prepare_categorical_map_null_map():
    print("Testing test_prepare_categorical_map_null_map...")
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "country",
        "color_map": None 
    }
    
    attr_map = {"country": 1}
    values_map = {1: {1: "A"}}
    
    try:
        result = StyleService.prepare_categorical_map(config, attr_map, values_map)
        print("Success!", result)
    except AttributeError as e:
        print("Caught expected error!")
        traceback.print_exc()
    except Exception as e:
        print(f"Caught unexpected error: {type(e)}")
        traceback.print_exc()

def test_prepare_categorical_map_missing_map():
    print("\nTesting test_prepare_categorical_map_missing_map...")
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "country"
        # color_map is missing
    }
    
    attr_map = {"country": 1}
    values_map = {1: {1: "A"}}
    
    try:
        result = StyleService.prepare_categorical_map(config, attr_map, values_map)
        print("Success!", result)
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    test_prepare_categorical_map_null_map()
    test_prepare_categorical_map_missing_map()
