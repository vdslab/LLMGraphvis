"""Subgraph reuse must key on the node set, and node_filter must match text values.

Both were silent wrong answers: the second community extraction returned the
first community's subgraph, and filtering a community label "1" found nothing.
"""

from unittest.mock import patch

import networkx as nx

from app.logic import community
from app.logic import filter as filter_logic
from app.schemas.filter import AttributeCondition
from common import models


def _barbell(db) -> int:
    net = models.Network(name="Barbell")
    db.add(net)
    db.commit()
    db.refresh(net)
    graph = nx.barbell_graph(5, 0)  # two five-node cliques, one bridge
    for n in graph:
        db.add(models.Node(network_id=net.id, node_id=str(n), label=f"N{n}"))
    db.commit()
    ids = {n.node_id: n.id for n in db.query(models.Node).filter_by(network_id=net.id)}
    for u, v in graph.edges:
        db.add(
            models.Edge(
                network_id=net.id,
                edge_id=f"{u}-{v}",
                source_node_id=ids[str(u)],
                target_node_id=ids[str(v)],
            )
        )
    db.commit()
    return net.id


def _node_ids(db, network_id):
    return {n.node_id for n in db.query(models.Node).filter_by(network_id=network_id)}


def test_same_named_filter_subgraphs_are_not_reused_across_node_sets(db):
    nid = _barbell(db)
    attr = community.calculate_community(nid, "louvain", db, seed=42)

    def extract(label):
        condition = AttributeCondition(attribute_name=attr, categories=[label])
        return filter_logic.create_subgraph_by_filter(
            nid, [condition], "Filtered", db, preserve_layout=True
        )["new_network_id"]

    first, second = extract("0"), extract("1")

    assert first != second
    assert _node_ids(db, first).isdisjoint(_node_ids(db, second))


def test_identical_request_still_reuses_the_existing_subgraph(db):
    nid = _barbell(db)
    attr = community.calculate_community(nid, "louvain", db, seed=42)
    condition = AttributeCondition(attribute_name=attr, categories=["0"])

    first = filter_logic.create_subgraph_by_filter(
        nid, [condition], "Filtered", db, preserve_layout=True
    )
    again = filter_logic.create_subgraph_by_filter(
        nid, [condition], "Filtered", db, preserve_layout=True
    )

    assert first["new_network_id"] == again["new_network_id"]


def test_node_filter_matches_numeric_looking_text_and_reports_the_total(db, monkeypatch):
    from app.mcp.tools.node.operations import node_filter

    nid = _barbell(db)
    attr = community.calculate_community(nid, "louvain", db, seed=42)
    monkeypatch.setattr(db, "close", lambda: None)

    with patch("app.core.database.SessionLocal", return_value=db):
        result = node_filter(network_id=nid, attribute_name=attr, value="1", limit=2)

    assert result["count"] == 5
    assert result["truncated"] is True
    assert len(result["nodes"]) == 2
