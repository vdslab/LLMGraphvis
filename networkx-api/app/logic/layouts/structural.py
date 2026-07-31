"""Layouts driven by a structural property or a node attribute.

The partition layouts need work done before networkx is called: the user names a
node *attribute*, but nx wants an explicit node list (`nodes`) or an attribute
already present on the graph (`subset_key`). That translation is each layout's
own business, so it lives here as its `prepare` step.
"""

import networkx as nx

from .base import register


def prepare_bipartite(G, network_id, overrides, db):
    """Turn `partition_attribute` (+ optional `partition_value`) into `nodes`."""
    from ..attributes import load_node_attribute_values

    partition_attr = overrides.pop("partition_attribute", None)
    partition_value = overrides.pop("partition_value", None)

    if overrides.get("nodes"):
        return
    if not partition_attr:
        raise ValueError(
            "layout_bipartite needs either `partition_attribute` (the node "
            "attribute that splits the graph into two sides) or an explicit "
            "`nodes` list."
        )

    values = load_node_attribute_values(network_id, partition_attr, db)
    if not values:
        raise ValueError(
            f"Node attribute '{partition_attr}' has no values on network "
            f"{network_id}."
        )

    distinct = sorted({str(v) for v in values.values()})
    if partition_value is None:
        if len(distinct) != 2:
            raise ValueError(
                f"'{partition_attr}' has {len(distinct)} distinct values "
                f"({', '.join(distinct[:5])}...), so it does not define two sides. "
                f"Pass `partition_value` to choose which value forms one side, or "
                f"use layout_multipartite for more than two groups."
            )
        partition_value = distinct[0]

    side = [n for n in G.nodes if str(values.get(n)) == str(partition_value)]
    if not side or len(side) == len(G.nodes):
        raise ValueError(
            f"No usable split: '{partition_attr}' == '{partition_value}' selects "
            f"{len(side)} of {len(G.nodes)} nodes. One side would be empty."
        )
    overrides["nodes"] = side


def prepare_multipartite(G, network_id, overrides, db):
    """Attach `subset_attribute` to the graph's nodes and name it `subset_key`.

    build_graph_from_db loads no node attributes, so the attribute has to be
    fetched and set on the graph before networkx can see it.
    """
    from ..attributes import load_node_attribute_values

    subset_attr = overrides.pop("subset_attribute", None)

    if overrides.get("subset_key"):
        return
    if not subset_attr:
        raise ValueError(
            "layout_multipartite needs `subset_attribute`: the node attribute "
            "whose distinct values define the layers."
        )

    values = load_node_attribute_values(network_id, subset_attr, db)
    if not values:
        raise ValueError(
            f"Node attribute '{subset_attr}' has no values on network {network_id}."
        )

    missing = [n for n in G.nodes if n not in values]
    if missing:
        # nx raises an opaque KeyError if any node lacks the subset key.
        raise ValueError(
            f"{len(missing)} of {len(G.nodes)} nodes have no '{subset_attr}' value, "
            f"so they cannot be assigned to a layer. Use an attribute that every "
            f"node has, or extract a subgraph where it is fully populated."
        )

    for node in G.nodes:
        G.nodes[node][subset_attr] = values[node]
    overrides["subset_key"] = subset_attr


@register(
    "bipartite",
    params={"nodes", "align", "scale", "center", "aspect_ratio"},
    prepare=prepare_bipartite,
)
def bipartite(G, params):
    return nx.bipartite_layout(G, **params)


@register(
    "multipartite",
    params={"subset_key", "align", "scale", "center"},
    prepare=prepare_multipartite,
)
def multipartite(G, params):
    return nx.multipartite_layout(G, **params)


@register("planar", params={"scale", "center"})
def planar(G, params):
    try:
        return nx.planar_layout(G, **params)
    except nx.NetworkXException as e:
        # nx raises for non-planar input. Most real graphs are non-planar, so
        # this is the expected failure rather than an exceptional one, and it
        # deserves a message that says what to do instead.
        raise ValueError(
            "This graph is not planar, so it cannot be drawn without edge "
            "crossings. Use a force-directed layout (forceatlas2 or spring) "
            f"instead. (networkx: {e})"
        ) from e


@register("bfs", params={"start", "align", "scale", "center"})
def bfs(G, params):
    return nx.bfs_layout(G, **params)
