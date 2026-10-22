"""Numeric mappings: transform, explicit range, and uniform edge styles (ADR 0029)."""

import pytest
from app.logic.style_service import DEFAULT_EDGE_COLOR, StyleService
from app.schemas.visualization import EdgeColorConfig, NodeSizeConfig
from pydantic import ValidationError

ATTR = {"score": 1}
# A skewed metric: most nodes near zero, one outlier (like betweenness).
SKEWED = {i: {1: v} for i, v in enumerate([0.0, 0.0, 0.01, 0.02, 0.03, 1.0], 1)}
SIZE_RANGE = {"min": 0.0, "max": 100.0, "default": 7.0}


def _stats(**config):
    return StyleService.calculate_stats({"attribute": "score", **config}, ATTR, SKEWED)


def _size(db_id, **config):
    config = {"attribute": "score", "min": 0.0, "max": 100.0, **config}
    return StyleService.resolve_node_size(
        db_id, config, _stats(**config), ATTR, SKEWED, SIZE_RANGE
    )


def test_linear_keeps_the_old_proportional_mapping():
    assert _size(4) == pytest.approx(2.0)
    assert _size(6) == pytest.approx(100.0)


def test_log_separates_values_a_linear_scale_crushes():
    linear = [_size(i) for i in (3, 4, 5)]
    log = [_size(i, transform="log") for i in (3, 4, 5)]
    assert max(log) - min(log) > 5 * (max(linear) - min(linear))
    assert _size(1, transform="log") == pytest.approx(0.0)
    assert _size(6, transform="log") == pytest.approx(100.0)


def test_rank_spreads_by_order_and_ties_share_a_position():
    sizes = [_size(i, transform="rank") for i in range(1, 7)]
    assert sizes[0] == sizes[1]
    assert sizes == sorted(sizes)
    assert sizes[-1] == pytest.approx(100.0)
    assert sizes[3] - sizes[2] == pytest.approx(sizes[4] - sizes[3])


def test_value_max_clamps_outliers_to_the_top():
    assert _size(5, value_max=0.03) == pytest.approx(100.0)
    assert _size(6, value_max=0.03) == pytest.approx(100.0)
    assert _size(4, value_max=0.03) == pytest.approx(200 / 3)


def test_stats_report_the_mapped_range():
    stats = _stats(value_min=0.01, value_max=0.5)
    assert (stats.valid, stats.min, stats.max) == (True, 0.01, 0.5)
    assert tuple(stats[:3]) == (True, 0.01, 0.5)


def test_a_range_beside_the_data_is_refused():
    with pytest.raises(ValueError, match="value_min"):
        _stats(value_min=2.0)


def test_schema_rejects_an_inverted_range():
    with pytest.raises(ValidationError):
        NodeSizeConfig(attribute="score", value_min=1.0, value_max=0.5)


def test_color_follows_the_transform():
    config = {
        "attribute": "score",
        "scale_type": "LINEAR",
        "gradient": ["#000000", "#ffffff"],
    }

    def color(db_id, **extra):
        conf = {**config, **extra}
        return StyleService.resolve_node_color(
            db_id, str(db_id), conf, _stats(**extra), ATTR, SKEWED, {}, {}, {}
        )

    def gap(**extra):  # brightness difference between 0.01 and 0.03
        return int(color(5, **extra)[1:3], 16) - int(color(3, **extra)[1:3], 16)

    assert gap(transform="log") > 5 * gap()


def test_edge_color_without_attribute_is_uniform():
    config = EdgeColorConfig(default_color="#123456", opacity=0.6).model_dump()
    stats = StyleService.calculate_stats(config, {}, {})
    assert StyleService.resolve_edge_color(1, config, stats, {}, {}) == "#123456"
    assert StyleService.resolve_edge_color(1, {}, stats, {}, {}) == DEFAULT_EDGE_COLOR


def test_edge_categorical_color_needs_no_numeric_values():
    config = {
        "attribute": "kind",
        "scale_type": "CATEGORICAL",
        "color_map": {"a": "#ff0000"},
    }
    attrs, values = {"kind": 1}, {1: {1: "a"}, 2: {1: "b"}}
    stats = StyleService.calculate_stats(config, attrs, values)
    assert StyleService.resolve_edge_color(1, config, stats, attrs, values) == "#ff0000"
    assert (
        StyleService.resolve_edge_color(2, config, stats, attrs, values)
        == DEFAULT_EDGE_COLOR
    )


def test_edge_width_default_applies_without_attribute():
    config = {"attribute": None, "default": 0.4}
    stats = StyleService.calculate_stats(config, {}, {})
    width = StyleService.resolve_edge_width(
        1, config, stats, {}, {}, {"min": 1, "max": 5, "default": 1}
    )
    assert width == 0.4
