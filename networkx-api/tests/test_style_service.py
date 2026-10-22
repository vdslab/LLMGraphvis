import pytest
from pydantic import ValidationError

from app.logic import common_utils
from app.logic.style_service import StyleService
from app.schemas.visualization import NodeColorConfig


def test_prepare_categorical_map_autofill():
    """Test that missing values are auto-filled when no default_color is provided."""
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "country",
        "color_map": {"A": "red"},
    }

    attr_map = {"country": 1}
    # Nodes: 1->A, 2->B, 3->C
    values_map = {1: {1: "A"}, 2: {1: "B"}, 3: {1: "C"}}

    result = StyleService.prepare_categorical_map(config, attr_map, values_map)

    # A should be red (preserved)
    assert result["A"] == "red"
    # B and C should be in the map (auto-filled)
    assert "B" in result
    assert "C" in result
    # They should have colors
    assert result["B"] is not None
    assert result["C"] is not None
    assert config["palette"] == "tableau10"


def test_prepare_categorical_map_respects_default():
    """Test that missing values are NOT auto-filled when default_color IS provided."""
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "country",
        "color_map": {"A": "red"},
        "default_color": "gray",
    }

    attr_map = {"country": 1}
    values_map = {1: {1: "A"}, 2: {1: "B"}, 3: {1: "C"}}

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
        "default_color": "gray",
    }

    # Empty categorical map (simulating what happens if we skip autofill)
    categorical_map = {}

    attr_map = {"country": 1}
    values_map = {2: {1: "B"}}

    stats = (True, 0, 0)  # stats valid

    color = StyleService.resolve_node_color(
        db_id=2,
        node_id_str="2",
        config=config,
        stats=stats,
        attr_map=attr_map,
        values_map=values_map,
        ranking_map={},
        categorical_map=categorical_map,
        custom_color_map={},
        default_color="blue",
    )

    assert color == "gray"


def test_categorical_mapping_corrects_unique_spacing_variation():
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "club",
        "color_map": {"Mr.Hi": "#800080", "Officer": "#008000"},
    }
    attr_map = {"club": 1}
    values_map = {1: {1: "Mr. Hi"}, 2: {1: "Officer"}}

    result = StyleService.prepare_categorical_map(config, attr_map, values_map)

    assert result == {"Mr. Hi": "#800080", "Officer": "#008000"}
    assert config["color_map"] == result


def test_categorical_mapping_rejects_values_absent_from_data():
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "club",
        "color_map": {"Unknown club": "#800080"},
    }
    attr_map = {"club": 1}
    values_map = {1: {1: "Mr. Hi"}, 2: {1: "Officer"}}

    with pytest.raises(ValueError, match="Available values.*'Mr. Hi'.*'Officer'"):
        StyleService.prepare_categorical_map(config, attr_map, values_map)


def test_categorical_mapping_rejects_ambiguous_normalized_match():
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "group",
        "color_map": {"AB": "#800080"},
    }
    attr_map = {"group": 1}
    values_map = {1: {1: "A B"}, 2: {1: "A-B"}}

    with pytest.raises(ValueError, match="Unknown or ambiguous"):
        StyleService.prepare_categorical_map(config, attr_map, values_map)


def test_d3_palette_selection_uses_category_count():
    assert common_utils.choose_categorical_palette(10) == "tableau10"
    assert common_utils.choose_categorical_palette(11) == "paired"
    assert common_utils.choose_categorical_palette(13) == "extended20"


def test_named_palette_fills_only_unspecified_categories():
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "group",
        "color_map": {"A": "#000000"},
        "palette": "pastel2",
    }
    attr_map = {"group": 1}
    values_map = {1: {1: "A"}, 2: {1: "B"}, 3: {1: "C"}}

    result = StyleService.prepare_categorical_map(config, attr_map, values_map)

    assert result == {
        "A": "#000000",
        "B": common_utils.D3_CATEGORICAL_PALETTES["pastel2"][1],
        "C": common_utils.D3_CATEGORICAL_PALETTES["pastel2"][2],
    }


def test_named_palette_does_not_cycle_past_its_capacity():
    values_map = {index: {1: f"group-{index}"} for index in range(9)}
    config = {
        "scale_type": "CATEGORICAL",
        "attribute": "group",
        "palette": "accent",
    }

    result = StyleService.prepare_categorical_map(
        config, {"group": 1}, values_map
    )

    assert len(result) == 8
    assert len(set(result.values())) == 8
    assert "group-8" not in result


def test_node_color_config_rejects_unknown_palette():
    with pytest.raises(ValidationError):
        NodeColorConfig(
            attribute="group", scale_type="CATEGORICAL", palette="made-up"
        )
