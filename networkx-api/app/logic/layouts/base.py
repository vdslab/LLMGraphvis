"""The layout registry: one entry per layout algorithm.

Everything that differs between layouts — which networkx function runs it, which
parameters it accepts, how those parameters are auto-tuned to graph size, what an
edge weight *means* to it, and any preparation it needs — is declared next to
that layout's own function. Before this, the same thirteen layouts were spread
across four parallel structures (a params allowlist, a tuning if/elif chain, two
weight-policy sets, and a dispatch if/elif chain) that had to be kept in step by
hand; adding a layout meant editing all four and forgetting one was silent.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, FrozenSet, Optional, Tuple


class WeightRole(Enum):
    """What an edge weight means to a layout — which decides the default.

    The distinction is not cosmetic. A weight that means *strength* can be turned
    on automatically for a weighted network, because that is what the data
    already says. A weight that means *distance* would then be read backwards,
    drawing the most strongly connected nodes furthest apart, so it must be asked
    for explicitly.
    """

    NONE = "none"          # the algorithm has no weight concept at all
    STRENGTH = "strength"  # heavier = pulled closer together
    DISTANCE = "distance"  # heavier = placed further apart


@dataclass(frozen=True)
class LayoutSpec:
    """Everything the orchestrator needs to know about one layout."""

    name: str
    compute: Callable          # (G, params) -> {node: (x, y)}
    params: FrozenSet[str]     # allowlist of kwargs that may reach networkx
    weight_role: WeightRole = WeightRole.NONE
    tune: Optional[Callable] = None     # (G) -> dict of size-derived defaults
    prepare: Optional[Callable] = None  # (G, network_id, overrides, db) -> None
    aliases: Tuple[str, ...] = ()

    @property
    def supports_warm_start(self) -> bool:
        """Whether `init_from_layout` can seed this layout with `pos`."""
        return "pos" in self.params

    @property
    def accepts_weight(self) -> bool:
        return self.weight_role is not WeightRole.NONE


SPECS: Dict[str, LayoutSpec] = {}
_ALIASES: Dict[str, str] = {}


def register(
    name: str,
    *,
    params,
    weight_role: WeightRole = WeightRole.NONE,
    tune: Optional[Callable] = None,
    prepare: Optional[Callable] = None,
    aliases=(),
):
    """Declare a layout. Decorates the function that calls networkx.

    The allowlist matters twice over: a kwarg a given nx function does not accept
    would raise TypeError from inside networkx (e.g. `scale` on random_layout,
    which has no such parameter), and a kwarg we advertise but drop would be a
    parameter that silently does nothing. `tests/test_layout_parameters.py`
    checks every name here against the installed networkx signature.
    """

    def decorator(fn: Callable) -> Callable:
        spec = LayoutSpec(
            name=name,
            compute=fn,
            params=frozenset(params),
            weight_role=weight_role,
            tune=tune,
            prepare=prepare,
            aliases=tuple(aliases),
        )
        SPECS[name] = spec
        for alias in spec.aliases:
            _ALIASES[alias] = name
        return fn

    return decorator


def canonical_name(layout_name: str) -> str:
    """Map an alias ('force_directed', 'circle', ...) to the registered name."""
    return _ALIASES.get(layout_name, layout_name)


def get_spec(layout_name: str) -> LayoutSpec:
    name = canonical_name(layout_name)
    try:
        return SPECS[name]
    except KeyError:
        raise ValueError(
            f"Unknown layout algorithm: {layout_name}. "
            f"Supported: {', '.join(sorted(SPECS))}."
        ) from None


def layout_names():
    return sorted(SPECS)


def param_keys() -> Dict[str, FrozenSet[str]]:
    """The per-layout allowlist, in the shape the older code exposed it."""
    return {name: spec.params for name, spec in SPECS.items()}
