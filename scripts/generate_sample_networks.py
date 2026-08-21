"""Regenerate the bundled GraphML samples from NetworkX's named graphs.

Run this from an environment that has the NetworkX API dependencies installed.
The generated files are committed so loading a sample never needs NetworkX in
the backend process or network access at runtime.
"""

from pathlib import Path

import networkx as nx


OUTPUT_DIR = (
    Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "samples"
)


def _add_labels(graph: nx.Graph, prefix: str | None = None) -> nx.Graph:
    for node in graph:
        graph.nodes[node]["label"] = f"{prefix} {int(node) + 1}" if prefix else str(node)
    return graph


def _karate_club() -> nx.Graph:
    graph = _add_labels(nx.karate_club_graph(), "Member")
    graph.name = "Zachary's Karate Club"
    return graph


def _les_miserables() -> nx.Graph:
    graph = _add_labels(nx.les_miserables_graph())
    graph.name = "Les Miserables"
    return graph


def _florentine_families() -> nx.Graph:
    graph = _add_labels(nx.florentine_families_graph())
    graph.name = "Florentine Families"
    return graph


def _davis_southern_women() -> nx.Graph:
    graph = nx.davis_southern_women_graph()
    women = set(graph.graph.pop("top"))
    events = set(graph.graph.pop("bottom"))
    _add_labels(graph)
    nx.set_node_attributes(
        graph,
        {node: "woman" if node in women else "event" for node in graph},
        "node_type",
    )
    assert women | events == set(graph)
    graph.name = "Davis Southern Women"
    return graph


SAMPLES = {
    "karate-club.graphml": _karate_club,
    "les-miserables.graphml": _les_miserables,
    "florentine-families.graphml": _florentine_families,
    "davis-southern-women.graphml": _davis_southern_women,
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, build_graph in SAMPLES.items():
        nx.write_graphml(
            build_graph(),
            OUTPUT_DIR / filename,
            encoding="utf-8",
            named_key_ids=True,
        )


if __name__ == "__main__":
    main()
