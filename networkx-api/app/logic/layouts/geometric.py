"""Layouts that place nodes by geometry rather than by structure.

None of these read edge data at all, so none of them take a weight.
"""

import networkx as nx

from .base import register


@register("circular", params={"scale", "center"}, aliases=("circle",))
def circular(G, params):
    return nx.circular_layout(G, **params)


@register("shell", params={"nlist", "rotate", "scale", "center"})
def shell(G, params):
    return nx.shell_layout(G, **params)


@register("spiral", params={"scale", "center", "resolution", "equidistant"})
def spiral(G, params):
    return nx.spiral_layout(G, **params)


@register(
    # NOTE: nx.random_layout(G, center=None, dim=2, seed=None) has no `scale`
    # parameter, unlike the other three geometric layouts.
    "random",
    params={"center", "seed"},
    # `seed` used to be hardcoded at the call site, which made passing it as an
    # override raise TypeError for a duplicate keyword argument. As a tuned
    # default it is overridable like any other parameter.
    tune=lambda G: {"seed": 42},
)
def random(G, params):
    return nx.random_layout(G, **params)
