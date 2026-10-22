"""The layout registry: one entry per layout algorithm.

Everything that differs between layouts — which networkx function runs it, which
parameters it accepts, how those parameters are auto-tuned to graph size, what an
edge weight *means* to it, and any preparation it needs — is declared next to
that layout's own function. Before this, the same thirteen layouts were spread
across four parallel structures (a params allowlist, a tuning if/elif chain, two
weight-policy sets, and a dispatch if/elif chain) that had to be kept in step by
hand; adding a layout meant editing all four and forgetting one was silent.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Tuple


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
class Knob:
    """A parameter worth moving to fix a readability problem, and which way.

    `fixes` maps an issue label from `layout_quality.diagnose` to a direction:
    +1 raises the value (or turns a toggle on), -1 lowers it (or turns it off),
    0 means it helps but the direction depends on the graph, so try both.
    The search in `layout_optimizer` and the recommended ranges shown to the
    model both come from here, so a range is stated once, next to the layout.

    `relative` ranges are factors of the tuned value (e.g. spring's `k`, whose
    sensible scale depends on the node count); otherwise they are absolute.
    `requires` names other parameters that must hold for this one to take effect
    (spring's `gravity` only acts with method='energy').
    """

    param: str
    low: float = 0.0
    high: float = 1.0
    log: bool = True
    integer: bool = False
    toggle: bool = False
    relative: bool = False
    fixes: Mapping[str, int] = field(default_factory=dict)
    requires: Mapping[str, Any] = field(default_factory=dict)

    def bounds(self, tuned_value) -> Tuple[float, float]:
        if self.relative and isinstance(tuned_value, (int, float)) and tuned_value:
            return self.low * tuned_value, self.high * tuned_value
        return self.low, self.high

    def describe(self, tuned_value=None) -> Dict[str, Any]:
        """The knob as the model sees it in `layout_suggest_parameters`."""
        info: Dict[str, Any] = {"param": self.param}
        if self.toggle:
            info["type"] = "toggle"
        else:
            low, high = self.bounds(tuned_value)
            info["range"] = [_round(low), _round(high)]
            info["scale"] = "log" if self.log else "linear"
        words = ("on", "off") if self.toggle else ("raise", "lower")
        info["fixes"] = {
            issue: words[0] if d > 0 else words[1] if d < 0 else "either way"
            for issue, d in self.fixes.items()
        }
        if self.requires:
            info["requires"] = dict(self.requires)
        return info


def _round(value: float) -> float:
    return float(f"{value:.3g}")


# `tune` returns the parameters and one note per rule that moved a value away
# from its plain default; the notes reach the model in the tool's reply.
Tuning = Tuple[Dict[str, Any], List[str]]


@dataclass(frozen=True)
class LayoutSpec:
    """Everything the orchestrator needs to know about one layout."""

    name: str
    compute: Callable          # (G, params) -> {node: (x, y)}
    params: FrozenSet[str]     # allowlist of kwargs that may reach networkx
    weight_role: WeightRole = WeightRole.NONE
    tune: Optional[Callable] = None     # (G, GraphProfile) -> Tuning
    prepare: Optional[Callable] = None  # (G, network_id, overrides, db) -> None
    aliases: Tuple[str, ...] = ()
    knobs: Tuple[Knob, ...] = ()

    def tuned(self, G, profile) -> Tuning:
        """The profile-derived defaults and the notes explaining them."""
        if not self.tune:
            return {}, []
        return self.tune(G, profile)

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
    knobs=(),
):
    """Declare a layout. Decorates the function that calls networkx.

    The allowlist matters twice over: a kwarg a given nx function does not accept
    would raise TypeError from inside networkx (e.g. `scale` on random_layout,
    which has no such parameter), and a kwarg we advertise but drop would be a
    parameter that silently does nothing. `tests/test_layout_parameters.py`
    checks every name here against the installed networkx signature.

    `knobs` declare which parameters fix which readability problem (see `Knob`);
    a layout with none cannot be tuned by `layout_suggest_parameters`.
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
            knobs=tuple(knobs),
        )
        unknown = {k.param for k in spec.knobs} - spec.params
        if unknown:
            raise ValueError(f"Layout '{name}' declares knobs it does not accept: {unknown}")
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
