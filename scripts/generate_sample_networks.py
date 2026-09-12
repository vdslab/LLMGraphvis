"""Regenerate the bundled GraphML samples from NetworkX's named graphs.

Run this from an environment that has the NetworkX API dependencies installed.
The generated files are committed so loading a sample never needs NetworkX in
the backend process or network access at runtime.

The samples also carry their meaning: a `<desc>` on the graph says what the
nodes and edges represent and where the data comes from, and a `<desc>` on every
`<key>` says what that attribute means. The importer reads both into the network
and attribute descriptions, which is how the agent learns what the data is about
before proposing an analysis. NetworkX does not write `<desc>` elements, so the
text below is injected into its output; a missing description fails the run
rather than shipping an unannotated sample.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict
from xml.sax.saxutils import escape

import networkx as nx


OUTPUT_DIR = (
    Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "samples"
)

# NetworkX emits every key as a self-closing element and opens exactly one
# graph, so a description can be appended to each without reindenting the file.
KEY_ELEMENT = re.compile(r'<key\b[^>]*attr\.name="(?P<name>[^"]+)"[^>]*?/>')
GRAPH_ELEMENT = re.compile(r"<graph\b[^>]*>")

# Dataset name is a NetworkX graph attribute, so it becomes a key like any other.
NAME_DESCRIPTION = "Dataset name."


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


@dataclass(frozen=True)
class Sample:
    """One bundled sample: how to build it and what it means."""

    filename: str
    build: Callable[[], nx.Graph]
    description: str
    attribute_descriptions: Dict[str, str] = field(default_factory=dict)


SAMPLES = (
    Sample(
        filename="karate-club.graphml",
        build=_karate_club,
        description=(
            "Zachary's Karate Club friendship network. Nodes represent members "
            "and edges represent their interactions. The imported club attribute "
            "records membership in Mr. Hi or Officer, not an algorithmically "
            "detected community. Edge weight counts the contexts in which two "
            "members interacted; it is not a distance. Source: "
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.karate_club_graph.html"
        ),
        attribute_descriptions={
            "weight": "Number of contexts in which the two members interacted.",
            "label": "Member identifier used as a display label.",
            "club": "Recorded club membership: Mr. Hi or Officer.",
        },
    ),
    Sample(
        filename="les-miserables.graphml",
        build=_les_miserables,
        description=(
            "Character coappearance network from Victor Hugo's Les Miserables. "
            "Nodes represent characters and edges represent coappearances. Edge "
            "weight is the coappearance weight supplied by NetworkX; it is not a "
            "distance. This sample has character labels but no imported faction "
            "or community membership. Source: "
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.les_miserables_graph.html"
        ),
        attribute_descriptions={
            "weight": "Coappearance weight supplied by the source network.",
            "label": "Character name.",
        },
    ),
    Sample(
        filename="florentine-families.graphml",
        build=_florentine_families,
        description=(
            "Florentine family marriage network. Nodes represent families and "
            "edges represent marriage ties. This sample contains family labels "
            "and connections, but no wealth, political power, or faction "
            "attributes. Source: "
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.florentine_families_graph.html"
        ),
        attribute_descriptions={
            "label": "Family name.",
        },
    ),
    Sample(
        filename="davis-southern-women.graphml",
        build=_davis_southern_women,
        description=(
            "Davis Southern Women attendance network. Nodes represent women or "
            "social events; an edge records attendance, not a direct friendship "
            "between women. The imported bipartite attribute distinguishes women "
            "(0) from events (1). The sample adds node_type with woman/event and "
            "display labels for readability. Source: "
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.davis_southern_women_graph.html"
        ),
        attribute_descriptions={
            "node_type": "Readable sample annotation of bipartite: woman or event.",
            "label": "Woman name or event identifier.",
            "bipartite": "Bipartite set: 0 for women, 1 for events.",
        },
    ),
)


def _describe_attributes(graphml: str, sample: Sample) -> str:
    """Give every `<key>` the description recorded for that attribute."""
    described: set[str] = set()

    def annotate(match: re.Match[str]) -> str:
        name = match.group("name")
        if name == "name":
            description = NAME_DESCRIPTION
        else:
            try:
                description = sample.attribute_descriptions[name]
            except KeyError:
                raise KeyError(
                    f"{sample.filename}: attribute '{name}' has no description. "
                    "Describe it in SAMPLES before regenerating."
                ) from None
        described.add(name)
        opening = match.group(0)[: -len("/>")].rstrip()
        return f"{opening}><desc>{escape(description)}</desc></key>"

    annotated = KEY_ELEMENT.sub(annotate, graphml)

    unused = set(sample.attribute_descriptions) - described
    if unused:
        raise KeyError(
            f"{sample.filename}: described attributes are absent from the graph: "
            f"{sorted(unused)}"
        )
    return annotated


def _describe_graph(graphml: str, sample: Sample) -> str:
    """Put the dataset's meaning and source on the graph element."""
    annotated, count = GRAPH_ELEMENT.subn(
        lambda match: f"{match.group(0)}\n<desc>{escape(sample.description)}</desc>\n",
        graphml,
        count=1,
    )
    if count != 1:
        raise ValueError(f"{sample.filename}: no graph element to describe")
    return annotated


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        path = OUTPUT_DIR / sample.filename
        nx.write_graphml(
            sample.build(),
            path,
            encoding="utf-8",
            named_key_ids=True,
        )
        graphml = path.read_text(encoding="utf-8")
        graphml = _describe_attributes(graphml, sample)
        graphml = _describe_graph(graphml, sample)
        path.write_text(graphml, encoding="utf-8")


if __name__ == "__main__":
    main()
