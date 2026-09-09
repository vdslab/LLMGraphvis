import networkx as nx
import pytest
from app.logic.importer import parse_and_save_graphml
from app.logic.utils.graph_builder import build_graph_from_db
from test_layout_parameters import setup_graph

from common import models


def test_parallel_import_rejected_before_any_write(db):
    graph = nx.MultiGraph()
    graph.add_edge("a", "b", weight=1)
    graph.add_edge("a", "b", weight=2)
    with pytest.raises(ValueError, match="Parallel edges"):
        parse_and_save_graphml(1, "\n".join(nx.generate_graphml(graph)), db)
    assert db.query(models.Network).count() == 0


def test_old_parallel_data_is_not_silently_collapsed(db):
    setup_graph(db)
    edge = db.query(models.Edge).first()
    db.add(
        models.Edge(
            network_id=1,
            edge_id="duplicate",
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            weight=2,
        )
    )
    db.commit()
    with pytest.raises(ValueError, match="Parallel edges"):
        build_graph_from_db(1, db)
