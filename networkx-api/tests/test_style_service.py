
import pytest
from app.logic.style_service import StyleService

def test_prepare_categorical_map_autofill():
    """Test that missing values are auto-filled when no default_color is provided."""
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "country",
        "color_map": {"A": "red"}
    }
    
    attr_map = {"country": 1}
    # Nodes: 1->A, 2->B, 3->C
    values_map = {
        1: {1: "A"},
        2: {1: "B"},
        3: {1: "C"}
    }
    
    result = StyleService.prepare_categorical_map(config, attr_map, values_map)
    
    # A should be red (preserved)
    assert result["A"] == "red"
    # B and C should be in the map (auto-filled)
    assert "B" in result
    assert "C" in result
    # They should have colors
    assert result["B"] is not None
    assert result["C"] is not None

def test_prepare_categorical_map_respects_default():
    """Test that missing values are NOT auto-filled when default_color IS provided."""
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "country",
        "color_map": {"A": "red"},
        "default_color": "gray"
    }
    
    attr_map = {"country": 1}
    values_map = {
        1: {1: "A"},
        2: {1: "B"},
        3: {1: "C"}
    }
    
    result = StyleService.prepare_categorical_map(config, attr_map, values_map)
    
    # A should be red
    assert result["A"] == "red"
    
    
    # B and C should be in the map (auto-filled because we now support hybrid mode)
    assert "B" in result
    assert "C" in result
    assert result["B"] is not None
    assert result["C"] is not None

def test_resolve_node_color_fallback():
    """Test that resolve_node_color falls back to default_color if value not in map."""
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "country",
        "default_color": "gray"
    }
    
    # Empty categorical map (simulating what happens if we skip autofill)
    categorical_map = {}
    
    attr_map = {"country": 1}
    values_map = {2: {1: "B"}}
    
    stats = (True, 0, 0) # stats valid
    
    color = StyleService.resolve_node_color(
        db_id=2, node_id_str="2", config=config, stats=stats,
        attr_map=attr_map, values_map=values_map,
        ranking_map={}, categorical_map=categorical_map, custom_color_map={},
        default_color="blue"
    )
    
    assert color == "gray"
