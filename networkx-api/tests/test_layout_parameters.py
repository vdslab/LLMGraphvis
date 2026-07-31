"""Tests for the expanded layout parameter surface.

Covers the three bugs that made parameters silently ineffective (spectral
dropping its params, random's hardcoded seed, layouts never seeing edge
weights), the per-layout allowlist, warm-starting, and the newly added
algorithms.
"""

import inspect
from unittest.mock import patch

import networkx as nx
import pytest


from app.logic.layout import (
    LAYOUT_PARAM_KEYS,
    calculate_layout,
    load_layout_positions,
)
from common import models


def setup_graph(db, network_id=1, n=6, weighted=False, attrs=None, weights=None):
    """A small path-plus-chord graph, optionally with weights and node attributes.

    `weights` gives one weight per edge explicitly (None entries stay NULL);
    `weighted=True` is the shorthand for the varying weights 1.0 .. n-1.
    """
    db.add(models.Network(id=network_id, name=f"Net {network_id}"))
    nodes = []
    for i in range(n):
        node = models.Node(network_id=network_id, node_id=f"n{i}")
        db.add(node)
        nodes.append(node)
    db.commit()

    node_map = {node.node_id: node.id for node in nodes}
    for i in range(n - 1):
        if weights is not None:
            weight = weights[i]
        else:
            weight = float(i + 1) if weighted else None
        db.add(
            models.Edge(
                network_id=network_id,
                source_node_id=node_map[f"n{i}"],
                target_node_id=node_map[f"n{i + 1}"],
                edge_id=f"e{i}",
                weight=weight,
            )
        )
    db.commit()

    if attrs:
        from app.logic.attributes import bulk_save_node_attributes

        for attr_name, values in attrs.items():
            data_type = "float" if all(
                isinstance(v, (int, float)) for v in values.values()
            ) else "string"
            bulk_save_node_attributes(
                network_id,
                attr_name,
                data_type,
                {node_map[k]: v for k, v in values.items()},
                db,
            )
        db.commit()
    return node_map


def stored_layouts(db, network_id, name):
    return db.query(models.NodeAttribute).filter_by(
        network_id=network_id, attribute_name=f"{name}_x"
    ).first()


# --------------------------------------------------------------------------
# The allowlist
# --------------------------------------------------------------------------


class TestLayoutParamKeys:
    def test_every_key_is_accepted_by_its_networkx_function(self):
        """An allowlisted key nx does not accept would raise TypeError at runtime."""
        fns = {
            "spring": nx.spring_layout,
            "forceatlas2": nx.forceatlas2_layout,
            "kamada_kawai": nx.kamada_kawai_layout,
            "spectral": nx.spectral_layout,
            "arf": nx.arf_layout,
            "circular": nx.circular_layout,
            "shell": nx.shell_layout,
            "spiral": nx.spiral_layout,
            "random": nx.random_layout,
            "bipartite": nx.bipartite_layout,
            "multipartite": nx.multipartite_layout,
            "planar": nx.planar_layout,
            "bfs": nx.bfs_layout,
        }
        assert set(fns) == set(LAYOUT_PARAM_KEYS), "allowlist and dispatch disagree"
        for name, keys in LAYOUT_PARAM_KEYS.items():
            accepted = set(inspect.signature(fns[name]).parameters)
            assert not (keys - accepted), (
                f"{name}: allowlisted but not in nx signature: {sorted(keys - accepted)}"
            )

    def test_random_has_no_scale(self):
        """nx.random_layout genuinely lacks `scale`, unlike the other geometrics."""
        assert "scale" not in LAYOUT_PARAM_KEYS["random"]

    def test_unsupported_override_is_dropped_not_raised(self, db):
        setup_graph(db)
        # `gravity` is a forceatlas2/spring parameter; circular has no such kwarg.
        calculate_layout(1, "circular", db, overrides={"gravity": 5.0})
        assert stored_layouts(db, 1, "circular") is not None


# --------------------------------------------------------------------------
# Bug fixes
# --------------------------------------------------------------------------


class TestSpectralParamsReachNetworkx:
    def test_spectral_receives_its_parameters(self, db):
        """Previously `nx.spectral_layout(G)` was called with no kwargs at all."""
        setup_graph(db)
        with patch("networkx.spectral_layout", wraps=nx.spectral_layout) as spy:
            calculate_layout(1, "spectral", db, overrides={"scale": 3.0})
        assert spy.call_args.kwargs.get("scale") == 3.0


class TestRandomSeedIsOverridable:
    def test_explicit_seed_does_not_collide_with_the_default(self, db):
        """Passing `seed` used to raise TypeError for a duplicate keyword."""
        setup_graph(db)
        calculate_layout(1, "random", db, overrides={"seed": 7})
        assert stored_layouts(db, 1, "random") is not None

    def test_different_seeds_produce_different_positions(self, db):
        setup_graph(db)
        calculate_layout(1, "random", db, overrides={"seed": 1})
        first = load_layout_positions(1, "random", db)
        calculate_layout(1, "random", db, overrides={"seed": 2}, force=True)
        second = load_layout_positions(1, "random", db)
        assert first != second

    def test_default_seed_is_reproducible(self, db):
        setup_graph(db)
        calculate_layout(1, "random", db)
        first = load_layout_positions(1, "random", db)
        calculate_layout(1, "random", db, force=True)
        assert load_layout_positions(1, "random", db) == first


def add_edge_attribute(db, network_id, name, values):
    """Attach a float edge attribute, `values` being one value per edge in order."""
    attr = models.EdgeAttribute(
        network_id=network_id, attribute_name=name, data_type="float"
    )
    db.add(attr)
    db.commit()
    edges = (
        db.query(models.Edge)
        .filter(models.Edge.network_id == network_id)
        .order_by(models.Edge.id)
        .all()
    )
    for edge, value in zip(edges, values):
        eav = models.EdgeAttributeValue(edge_id=edge.id, attribute_id=attr.id)
        db.add(eav)
        db.commit()
        db.add(
            models.EdgeFloatAttributeValue(
                edge_attribute_value_id=eav.id, float_value=float(value)
            )
        )
    db.commit()


def weights_seen_by(layout_name, nx_name, db, overrides=None, network_id=1):
    """Run a layout and report the edge-attribute payload networkx actually saw."""
    captured = {}
    real = getattr(nx, nx_name)

    def spy(G, **kwargs):
        captured["edge_data"] = [d for _, _, d in G.edges(data=True)]
        captured["weight_kwarg"] = kwargs.get("weight")
        return real(G, **kwargs)

    with patch(f"networkx.{nx_name}", side_effect=spy):
        captured["info"] = calculate_layout(
            network_id, layout_name, db, overrides=overrides
        )
    return captured


class TestEdgeWeights:
    def test_weight_parameter_builds_a_weighted_graph(self, db):
        """Without this the graph carried no weight attribute, so nx's default
        weight='weight' silently degraded to unweighted."""
        setup_graph(db, weighted=True)
        seen = weights_seen_by("spring", "spring_layout", db, {"weight": "weight"})
        assert all("weight" in d for d in seen["edge_data"])

    def test_varying_weights_are_used_without_being_asked(self, db):
        """The whole point: a weighted file is laid out weighted by default."""
        setup_graph(db, weighted=True)
        seen = weights_seen_by("spring", "spring_layout", db)
        assert all(d["weight"] for d in seen["edge_data"])
        assert seen["weight_kwarg"] == "weight"
        assert "automatically" in seen["info"]["weight_note"]

    def test_forceatlas2_and_spectral_are_weighted_by_default_too(self, db):
        setup_graph(db, weighted=True)
        for layout_name, nx_name in (
            ("forceatlas2", "forceatlas2_layout"),
            ("spectral", "spectral_layout"),
        ):
            seen = weights_seen_by(layout_name, nx_name, db)
            assert seen["weight_kwarg"] == "weight", layout_name

    def test_uniform_weights_are_left_alone(self, db):
        """Every edge weighing the same lays out identically either way, so the
        slower weighted path buys nothing."""
        setup_graph(db, weights=[2.0] * 5)
        seen = weights_seen_by("spring", "spring_layout", db)
        assert all(d == {} for d in seen["edge_data"])
        assert seen["info"]["weight_note"] == ""

    def test_unweighted_network_stays_unweighted(self, db):
        setup_graph(db)
        seen = weights_seen_by("spring", "spring_layout", db)
        assert all(d == {} for d in seen["edge_data"])

    def test_non_positive_weights_are_not_used(self, db):
        """A zero or negative weight has no meaning as attraction strength."""
        setup_graph(db, weights=[0.0, 1.0, 2.0, 3.0, 4.0])
        seen = weights_seen_by("spring", "spring_layout", db)
        assert all(d == {} for d in seen["edge_data"])

    def test_weight_none_opts_out(self, db):
        setup_graph(db, weighted=True)
        seen = weights_seen_by("spring", "spring_layout", db, {"weight": "none"})
        assert all(d == {} for d in seen["edge_data"])
        assert seen["weight_kwarg"] is None
        assert "ignored" in seen["info"]["weight_note"]

    def test_opting_out_is_not_served_from_the_weighted_cache(self, db):
        """The resolved weight is part of the cache key, so the unweighted run
        recomputes instead of returning the weighted coordinates."""
        setup_graph(db, weighted=True)
        calculate_layout(1, "spring", db)
        weighted_pos = load_layout_positions(1, "spring", db)
        calculate_layout(1, "spring", db, overrides={"weight": "none"})
        assert load_layout_positions(1, "spring", db) != weighted_pos

    def test_kamada_kawai_is_not_weighted_by_default(self, db):
        """Its `weight` is a target distance, not a strength — enabling it
        automatically would push strongly connected nodes apart."""
        setup_graph(db, weighted=True)
        seen = weights_seen_by("kamada_kawai", "kamada_kawai_layout", db)
        assert seen["weight_kwarg"] is None
        assert "distances" in seen["info"]["weight_note"]

    def test_another_edge_attribute_can_be_the_weight(self, db):
        setup_graph(db, weighted=True)
        add_edge_attribute(db, 1, "strength", [9.0, 8.0, 7.0, 6.0, 5.0])
        seen = weights_seen_by("spring", "spring_layout", db, {"weight": "strength"})
        assert sorted(d["strength"] for d in seen["edge_data"]) == [5, 6, 7, 8, 9]
        assert seen["weight_kwarg"] == "strength"

    def test_unknown_weight_attribute_raises_instead_of_degrading(self, db):
        setup_graph(db, weighted=True)
        add_edge_attribute(db, 1, "strength", [9.0, 8.0, 7.0, 6.0, 5.0])
        with pytest.raises(ValueError, match="no edge attribute 'nope'"):
            calculate_layout(1, "spring", db, overrides={"weight": "nope"})

    def test_geometric_layouts_never_weight(self, db):
        """circular has no weight concept; resolution must not touch it."""
        setup_graph(db, weighted=True)
        seen = weights_seen_by("circular", "circular_layout", db)
        assert all(d == {} for d in seen["edge_data"])
        assert seen["info"]["weight_note"] == ""


class TestEdgeWeightSummary:
    def test_reports_the_range_of_varying_weights(self, db):
        from app.logic.utils.graph_builder import summarize_edge_weights

        setup_graph(db, weighted=True)
        summary = summarize_edge_weights(1, db)
        assert summary["is_informative"] is True
        assert (summary["min"], summary["max"]) == (1.0, 5.0)
        assert summary["distinct_values"] == 5

    def test_null_weights_read_as_one(self, db):
        """NULL becomes 1.0 at build time, so NULLs mixed with 3.0 do vary."""
        from app.logic.utils.graph_builder import summarize_edge_weights

        setup_graph(db, weights=[None, 3.0, 3.0, 3.0, 3.0])
        assert summarize_edge_weights(1, db)["is_informative"] is True

        setup_graph(db, network_id=2, weights=[None, 1.0, 1.0, 1.0, 1.0])
        assert summarize_edge_weights(2, db)["is_informative"] is False

    def test_empty_network_is_not_informative(self, db):
        from app.logic.utils.graph_builder import summarize_edge_weights

        db.add(models.Network(id=9, name="empty"))
        db.commit()
        summary = summarize_edge_weights(9, db)
        assert summary["edge_count"] == 0
        assert summary["is_informative"] is False


# --------------------------------------------------------------------------
# Warm start
# --------------------------------------------------------------------------


class TestWarmStart:
    def test_init_from_layout_seeds_positions(self, db):
        setup_graph(db)
        calculate_layout(1, "circular", db)
        seed_positions = load_layout_positions(1, "circular", db)
        assert seed_positions

        captured = {}
        real = nx.spring_layout

        def spy(G, **kwargs):
            captured["pos"] = kwargs.get("pos")
            return real(G, **kwargs)

        with patch("networkx.spring_layout", side_effect=spy):
            calculate_layout(
                1, "spring", db, overrides={"init_from_layout": "circular"}
            )
        assert captured["pos"] is not None
        assert set(captured["pos"]) == set(seed_positions)

    def test_missing_source_layout_is_a_clear_error(self, db):
        setup_graph(db)
        with pytest.raises(ValueError, match="No stored 'circular' layout"):
            calculate_layout(1, "spring", db, overrides={"init_from_layout": "circular"})

    def test_unsupported_layout_rejects_warm_start(self, db):
        setup_graph(db)
        calculate_layout(1, "circular", db)
        with pytest.raises(ValueError, match="cannot be warm-started"):
            calculate_layout(
                1, "spiral", db, overrides={"init_from_layout": "circular"}
            )

    def test_pos_is_digested_not_stored_verbatim(self, db):
        """A coordinate dict per node would bloat computation_params, but dropping
        it entirely would break invalidation — so it is reduced to a digest."""
        setup_graph(db)
        calculate_layout(1, "circular", db)
        calculate_layout(1, "spring", db, overrides={"init_from_layout": "circular"})
        params = stored_layouts(db, 1, "spring").computation_params
        assert isinstance(params["pos"], str)
        assert params["pos"].startswith("digest:")
        assert params["init_from_layout"] == "circular"

    def test_a_changed_starting_layout_invalidates_the_cache(self, db):
        """The digest has to actually track content, not just presence."""
        setup_graph(db)
        calculate_layout(1, "circular", db)
        calculate_layout(1, "spring", db, overrides={"init_from_layout": "circular"})
        first = stored_layouts(db, 1, "spring").computation_params["pos"]

        # Recompute the source layout with different positions, then warm-start again.
        calculate_layout(1, "circular", db, overrides={"scale": 5.0}, force=True)
        calculate_layout(
            1, "spring", db, overrides={"init_from_layout": "circular"}, force=True
        )
        assert stored_layouts(db, 1, "spring").computation_params["pos"] != first

    def test_warm_started_layout_hits_the_cache_on_repeat(self, db):
        """The digest must survive a float -> JSON -> float round trip."""
        setup_graph(db)
        calculate_layout(1, "circular", db)
        calculate_layout(1, "spring", db, overrides={"init_from_layout": "circular"})
        with patch("networkx.spring_layout") as spy:
            calculate_layout(1, "spring", db, overrides={"init_from_layout": "circular"})
        spy.assert_not_called()


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------


class TestCaching:
    def test_identical_call_hits_cache(self, db):
        setup_graph(db)
        calculate_layout(1, "spring", db, overrides={"k": 1.0})
        with patch("networkx.spring_layout") as spy:
            calculate_layout(1, "spring", db, overrides={"k": 1.0})
        spy.assert_not_called()

    def test_changed_parameter_misses_cache_without_force(self, db):
        """A genuine parameter change must recompute on its own."""
        setup_graph(db)
        calculate_layout(1, "spring", db, overrides={"k": 1.0})
        with patch("networkx.spring_layout", wraps=nx.spring_layout) as spy:
            calculate_layout(1, "spring", db, overrides={"k": 2.0})
        spy.assert_called_once()

    def test_force_recompute_bypasses_cache(self, db):
        setup_graph(db)
        calculate_layout(1, "spring", db)
        with patch("networkx.spring_layout", wraps=nx.spring_layout) as spy:
            calculate_layout(1, "spring", db, force=True)
        spy.assert_called_once()


# --------------------------------------------------------------------------
# New algorithms
# --------------------------------------------------------------------------


class TestNewAlgorithms:
    def test_arf(self, db):
        setup_graph(db)
        calculate_layout(1, "arf", db)
        assert stored_layouts(db, 1, "arf") is not None

    def test_planar_on_a_planar_graph(self, db):
        setup_graph(db)  # a path is planar
        calculate_layout(1, "planar", db)
        assert stored_layouts(db, 1, "planar") is not None

    def test_planar_on_a_non_planar_graph_explains_itself(self, db):
        """Most real graphs are non-planar, so this is the expected path."""
        db.add(models.Network(id=2, name="K5"))
        nodes = []
        for i in range(5):
            node = models.Node(network_id=2, node_id=f"k{i}")
            db.add(node)
            nodes.append(node)
        db.commit()
        node_map = {n.node_id: n.id for n in nodes}
        idx = 0
        for i in range(5):
            for j in range(i + 1, 5):
                db.add(models.Edge(
                    network_id=2,
                    source_node_id=node_map[f"k{i}"],
                    target_node_id=node_map[f"k{j}"],
                    edge_id=f"ke{idx}",
                ))
                idx += 1
        db.commit()

        with pytest.raises(ValueError, match="not planar"):
            calculate_layout(2, "planar", db)

    def test_bfs_from_a_root(self, db):
        setup_graph(db)
        calculate_layout(1, "bfs", db, overrides={"start": "n0"})
        assert stored_layouts(db, 1, "bfs") is not None

    def test_bipartite_from_an_attribute(self, db):
        setup_graph(
            db,
            n=6,
            attrs={"side": {f"n{i}": ("A" if i % 2 == 0 else "B") for i in range(6)}},
        )
        calculate_layout(1, "bipartite", db, overrides={"partition_attribute": "side"})
        assert stored_layouts(db, 1, "bipartite") is not None

    def test_bipartite_requires_a_partition(self, db):
        setup_graph(db)
        with pytest.raises(ValueError, match="partition_attribute"):
            calculate_layout(1, "bipartite", db)

    def test_bipartite_rejects_more_than_two_values_without_a_choice(self, db):
        setup_graph(
            db, n=6, attrs={"grp": {f"n{i}": f"g{i % 3}" for i in range(6)}}
        )
        with pytest.raises(ValueError, match="does not define two sides"):
            calculate_layout(1, "bipartite", db, overrides={"partition_attribute": "grp"})

    def test_bipartite_accepts_an_explicit_value_among_many(self, db):
        setup_graph(
            db, n=6, attrs={"grp": {f"n{i}": f"g{i % 3}" for i in range(6)}}
        )
        calculate_layout(
            1,
            "bipartite",
            db,
            overrides={"partition_attribute": "grp", "partition_value": "g0"},
        )
        assert stored_layouts(db, 1, "bipartite") is not None

    def test_bipartite_rejects_a_degenerate_split(self, db):
        setup_graph(db, n=4, attrs={"side": {f"n{i}": "same" for i in range(4)}})
        with pytest.raises(ValueError, match="One side would be empty"):
            calculate_layout(
                1,
                "bipartite",
                db,
                overrides={"partition_attribute": "side", "partition_value": "same"},
            )

    def test_multipartite_from_an_attribute(self, db):
        setup_graph(
            db, n=6, attrs={"level": {f"n{i}": float(i % 3) for i in range(6)}}
        )
        calculate_layout(
            1, "multipartite", db, overrides={"subset_attribute": "level"}
        )
        assert stored_layouts(db, 1, "multipartite") is not None

    def test_multipartite_requires_every_node_to_have_a_value(self, db):
        """nx raises an opaque KeyError; this must say what is wrong."""
        setup_graph(
            db, n=6, attrs={"level": {f"n{i}": float(i) for i in range(3)}}
        )
        with pytest.raises(ValueError, match="have no 'level' value"):
            calculate_layout(
                1, "multipartite", db, overrides={"subset_attribute": "level"}
            )

    def test_multipartite_requires_the_attribute(self, db):
        setup_graph(db)
        with pytest.raises(ValueError, match="subset_attribute"):
            calculate_layout(1, "multipartite", db)

    def test_unknown_layout_lists_the_supported_ones(self, db):
        setup_graph(db)
        with pytest.raises(ValueError, match="Unknown layout algorithm"):
            calculate_layout(1, "no_such_layout", db)


class TestAliasNormalization:
    @pytest.mark.parametrize(
        "alias,canonical",
        [
            ("forceatlas2_layout", "forceatlas2"),
            ("force-directed", "forceatlas2"),
            ("force_directed", "forceatlas2"),
            ("fruchterman_reingold", "spring"),
            ("circle", "circular"),
        ],
    )
    def test_aliases_store_under_the_canonical_name(self, db, alias, canonical):
        setup_graph(db)
        calculate_layout(1, alias, db)
        assert stored_layouts(db, 1, canonical) is not None


class TestLoadLayoutPositions:
    def test_returns_coordinates_keyed_by_node_id(self, db):
        setup_graph(db, n=4)
        calculate_layout(1, "circular", db)
        positions = load_layout_positions(1, "circular", db)
        assert set(positions) == {"n0", "n1", "n2", "n3"}
        assert all(len(v) == 2 for v in positions.values())

    def test_returns_empty_for_an_uncomputed_layout(self, db):
        setup_graph(db)
        assert load_layout_positions(1, "spiral", db) == {}
