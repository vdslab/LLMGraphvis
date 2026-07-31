"""Layouts derived from a matrix or a distance model: kamada_kawai, spectral."""

import networkx as nx

from .base import WeightRole, register


@register(
    "kamada_kawai",
    params={"dist", "pos", "weight", "scale", "center"},
    # The one layout whose `weight` is a target DISTANCE rather than a strength:
    # nx solves for a drawing where each edge's length matches its weight. Using
    # a similarity/strength weight here would place the most strongly connected
    # nodes furthest apart, so it is never applied automatically.
    weight_role=WeightRole.DISTANCE,
    tune=lambda G: {"scale": 1.0},
)
def kamada_kawai(G, params):
    """Kamada-Kawai. O(N^2) in time and memory, excellent global structure."""
    return nx.kamada_kawai_layout(G, **params)


@register(
    "spectral",
    params={"weight", "scale", "center"},
    weight_role=WeightRole.STRENGTH,
)
def spectral(G, params):
    """Eigenvectors of the Laplacian, built from the weighted adjacency matrix.

    NOTE: params used to be dropped at the call site here, so `weight`, `scale`
    and `center` had no effect whatsoever on a spectral layout.
    """
    return nx.spectral_layout(G, **params)
