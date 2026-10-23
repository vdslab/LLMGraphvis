"""Attribute role and measurement: inferred on import, exact for computed values.

`data_type` says only which table stores a value. The agent picks an encoding
from `measurement`, so a wrong or missing one shows up as a categorical code
drawn on a gradient, or a score split into unrelated colours.
"""

import pytest
from test_community import setup_clique_network

from app.logic import attribute_semantics as sem
from app.logic import attributes, network_metadata
from app.logic.community import calculate_community
from app.logic.importer import parse_and_save_graphml
from common import models

# --- Inference ---------------------------------------------------------------


@pytest.mark.parametrize(
    "values, expected",
    [
        ([1, 2, 3, 1, 2], sem.DISCRETE),
        ([0.1, 0.5, 0.25], sem.QUANTITATIVE),
        (list(range(sem.DISCRETE_MAX_DISTINCT + 1)), sem.QUANTITATIVE),
        ([True, False, True], sem.CATEGORICAL),
        (["true", "false"], sem.CATEGORICAL),
        (["Mr. Hi", "Officer", "Mr. Hi"], sem.CATEGORICAL),
        ([f"person {i}" for i in range(sem.DISCRETE_MAX_DISTINCT + 5)], sem.IDENTIFIER),
        (["x" * (sem.TEXT_MIN_MEAN_LENGTH + 1)] * 3, sem.TEXT),
        ([1, "N/A", 2], sem.CATEGORICAL),
        ([], None),
        ([None, None], None),
    ],
)
def test_infer_measurement(values, expected):
    assert sem.infer_measurement(values) == expected


def test_few_unique_strings_are_categories_not_identifiers():
    """Three distinct names among three nodes is too little to call identity."""
    assert sem.infer_measurement(["a", "b", "c"]) == sem.CATEGORICAL


@pytest.mark.parametrize(
    "source, role, measurement",
    [
        ("centrality:pagerank", sem.ROLE_METRIC, sem.QUANTITATIVE),
        ("community:louvain", sem.ROLE_COMMUNITY, sem.CATEGORICAL),
        ("layout:forceatlas2", sem.ROLE_COORDINATE, sem.QUANTITATIVE),
        (None, sem.ROLE_DATA, None),
    ],
)
def test_role_and_measurement_from_provenance(source, role, measurement):
    assert sem.role_for_source(source) == role
    assert sem.measurement_for_role(role) == measurement


# --- Encoding fit ------------------------------------------------------------


@pytest.mark.parametrize(
    "measurement, channel, scale, warns",
    [
        (sem.CATEGORICAL, "color", "linear", True),
        (sem.CATEGORICAL, "color", "ranking", True),
        (sem.CATEGORICAL, "size", None, True),
        (sem.IDENTIFIER, "width", None, True),
        (sem.QUANTITATIVE, "color", "categorical", True),
        (sem.CATEGORICAL, "color", "categorical", False),
        (sem.QUANTITATIVE, "color", "linear", False),
        (sem.QUANTITATIVE, "size", None, False),
        # Codes or counts: only the name can tell, so no warning either way.
        (sem.DISCRETE, "color", "linear", False),
        (sem.DISCRETE, "color", "categorical", False),
        (None, "size", None, False),
    ],
)
def test_encoding_note(measurement, channel, scale, warns):
    note = sem.encoding_note("attr", measurement, channel, scale)
    assert (note is not None) == warns


def test_summarize_parameters_keeps_only_what_a_reader_needs():
    params = {
        "algorithm": "louvain",
        "resolution": 1.0,
        "seed": None,
        "pos": "digest:0123456789abcdef",
        "nodes": [1, 2],
        "weight": "weight",
    }
    assert sem.summarize_parameters(params) == {"resolution": 1.0, "weight": "weight"}


# --- Persistence -------------------------------------------------------------

GRAPHML = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="club" for="node" attr.name="club" attr.type="string"/>
  <key id="group" for="node" attr.name="group" attr.type="int"/>
  <key id="score" for="node" attr.name="score" attr.type="double"/>
  <key id="kind" for="edge" attr.name="kind" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="a">
      <data key="club">X</data><data key="group">1</data>
      <data key="score">0.5</data>
    </node>
    <node id="b">
      <data key="club">Y</data><data key="group">2</data>
      <data key="score">1.25</data>
    </node>
    <node id="c">
      <data key="club">X</data><data key="group">1</data>
      <data key="score">2.75</data>
    </node>
    <edge source="a" target="b"><data key="kind">friend</data></edge>
    <edge source="b" target="c"><data key="kind">rival</data></edge>
  </graph>
</graphml>
"""


def _import(db):
    db.add(models.Network(id=1, name="Semantics"))
    db.commit()
    return parse_and_save_graphml(1, GRAPHML, db)


def _attr(db, network_id, name, model=models.NodeAttribute):
    return (
        db.query(model)
        .filter(model.network_id == network_id, model.attribute_name == name)
        .one()
    )


def test_import_stores_inferred_measurement_and_data_role(db):
    network_id = _import(db)

    assert _attr(db, network_id, "club").measurement == sem.CATEGORICAL
    assert _attr(db, network_id, "group").measurement == sem.DISCRETE
    assert _attr(db, network_id, "score").measurement == sem.QUANTITATIVE
    kind = _attr(db, network_id, "kind", models.EdgeAttribute)
    assert kind.measurement == sem.CATEGORICAL
    assert {a.role for a in db.query(models.NodeAttribute)} == {sem.ROLE_DATA}


def test_computed_attribute_gets_exact_role_and_measurement(db):
    setup_clique_network(db)
    name = calculate_community(1, "greedy_modularity", db)

    attr = _attr(db, 1, name)
    assert attr.role == sem.ROLE_COMMUNITY
    assert attr.measurement == sem.CATEGORICAL


def test_listing_carries_role_measurement_and_parameters(db):
    setup_clique_network(db)
    name = calculate_community(1, "louvain", db, seed=7)

    listed = {a["name"]: a for a in network_metadata.list_node_attributes(db, 1)}
    entry = listed[name]
    assert entry["role"] == sem.ROLE_COMMUNITY
    assert entry["measurement"] == sem.CATEGORICAL
    assert entry["parameters"].get("seed") == 7
    assert "algorithm" not in entry["parameters"]
    assert listed["label"]["measurement"] == sem.IDENTIFIER


def test_measurement_is_inferred_once_for_rows_that_predate_it(db):
    """Rows imported before measurements existed are filled in on first read."""
    network_id = _import(db)
    club = _attr(db, network_id, "club")
    club.measurement = None
    db.commit()

    assert attributes.get_measurement(network_id, "club", "node", db) == sem.CATEGORICAL
    db.refresh(club)
    assert club.measurement == sem.CATEGORICAL


def test_measurement_of_core_attributes(db):
    assert attributes.get_measurement(1, "weight", "edge", db) == sem.QUANTITATIVE
    assert attributes.get_measurement(1, "label", "node", db) == sem.IDENTIFIER
    assert attributes.get_measurement(1, "missing", "node", db) is None


def test_subgraph_copy_keeps_meaning_and_provenance(db):
    """Copied layout coordinates were once relabelled as imported data."""
    from app.logic.layout import calculate_layout
    from app.logic.subgraph import create_subgraph_from_nodes

    network_id = _import(db)
    calculate_layout(network_id, "circular", db)
    result = create_subgraph_from_nodes(
        network_id, ["a", "b"], db, preserve_layout=True
    )
    child = result["new_network_id"]

    assert _attr(db, child, "club").measurement == sem.CATEGORICAL
    x = _attr(db, child, "circular_x")
    assert (x.role, x.is_derived, x.derived_from) == (
        sem.ROLE_COORDINATE,
        True,
        "layout:circular",
    )


# --- Style tools -------------------------------------------------------------


@pytest.fixture
def bound(db, monkeypatch):
    """Route the tools' own sessions to the test session."""
    from app.core import database
    from app.mcp import tools

    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(database, "SessionLocal", lambda: db)
    network_id = _import(db)
    tools.layout_circular(network_id)
    return network_id


def test_style_tool_warns_when_scale_does_not_fit(bound):
    from app.mcp import tools

    vis = tools.visualization_set_node_size(bound, "club")
    assert "categorical" in vis["encoding_note"]

    vis = tools.visualization_set_node_color(bound, "score", "CATEGORICAL")
    assert "quantitative" in vis["encoding_note"]


def test_style_tool_is_silent_when_scale_fits(bound):
    from app.mcp import tools

    assert "encoding_note" not in tools.visualization_set_node_color(
        bound, "club", "CATEGORICAL"
    )
    assert "encoding_note" not in tools.visualization_set_node_size(bound, "score")
    assert "encoding_note" not in tools.visualization_set_edge_width(bound, "weight")


# --- Descriptions of computed values (ADR 0036) -------------------------------


@pytest.mark.parametrize(
    "centrality_type", ["degree", "betweenness", "closeness", "eigenvector", "pagerank"]
)
def test_computed_centrality_is_described(db, centrality_type):
    from app.logic.centrality import calculate_centrality

    setup_clique_network(db)
    calculate_centrality(1, centrality_type, db)
    name = (
        "pagerank" if centrality_type == "pagerank" else f"{centrality_type}_centrality"
    )

    assert _attr(db, 1, name).description == sem.describe_derived(
        f"centrality:{centrality_type}", _attr(db, 1, name).computation_params
    )
    assert _attr(db, 1, name).description


@pytest.mark.parametrize(
    "algorithm", ["louvain", "greedy_modularity", "label_propagation"]
)
def test_computed_community_is_described(db, algorithm):
    setup_clique_network(db)
    name = calculate_community(1, algorithm, db)

    assert "no order" in _attr(db, 1, name).description


@pytest.mark.parametrize(
    "source",
    [
        "centrality:in_degree",
        "centrality:out_degree",
        "centrality:clustering",
        "layout:forceatlas2",
    ],
)
def test_every_other_source_has_a_description(source):
    """Sources the end-to-end tests above cannot reach on an undirected clique."""
    assert sem.describe_derived(source, {})


def test_unknown_source_gets_no_description():
    assert sem.describe_derived("centrality:made_up", {}) is None
    assert sem.describe_derived(None, {}) is None


@pytest.mark.parametrize(
    "source, reading",
    [
        ("centrality:betweenness", "a distance"),
        ("centrality:closeness", "a distance"),
        ("centrality:pagerank", "tie strength"),
        ("community:louvain", "tie strength"),
    ],
)
def test_description_says_how_the_weight_was_read(source, reading):
    weighted = sem.describe_derived(source, {"weight": "weight"})
    assert f"'weight' was read as {reading}" in weighted
    assert "unweighted" in sem.describe_derived(source, {"weight": None})
    # An old row that never recorded the weight cannot say either.
    assert "weight" not in sem.describe_derived(source, {}).lower()


def test_description_follows_normalization_and_sampling():
    assert "Number of edges" in sem.describe_derived(
        "centrality:degree", {"normalized": False}
    )
    assert "0-1" in sem.describe_derived("centrality:degree", {"normalized": True})
    sampled = sem.describe_derived("centrality:betweenness", {"k": 10})
    assert "10 sampled nodes" in sampled


def test_rerun_rewrites_the_description(db):
    from app.logic.centrality import calculate_centrality

    setup_clique_network(db)
    calculate_centrality(1, "degree", db)
    calculate_centrality(1, "degree", db, normalized=False)

    assert "Number of edges" in _attr(db, 1, "degree_centrality").description


def test_listing_describes_rows_computed_before_descriptions(db):
    setup_clique_network(db)
    name = calculate_community(1, "louvain", db)
    row = _attr(db, 1, name)
    row.description = None
    db.commit()

    listed = {a["name"]: a for a in network_metadata.list_node_attributes(db, 1)}
    assert "no order" in listed[name]["description"]
    db.refresh(row)
    assert "no order" in row.description


def test_imported_description_is_left_alone(db):
    network_id = _import(db)
    club = _attr(db, network_id, "club")
    club.description = "Karate club the member joined"
    db.commit()

    listed = {
        a["name"]: a for a in network_metadata.list_node_attributes(db, network_id)
    }
    assert listed["club"]["description"] == "Karate club the member joined"
