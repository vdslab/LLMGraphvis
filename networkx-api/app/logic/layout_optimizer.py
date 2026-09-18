"""Search for layout parameters that fix what `layout_quality` found wrong.

The agent cannot see the drawing, and trial-and-error through the LLM costs a
round trip and a render per try. So the trial and error happens here: start
from the parameters the current layout used, move the knobs its layout declares
for each detected issue (see `Knob` in logic/layouts/base.py), score each
result the way it will be drawn, and return the best few.

Nothing is saved. Applying a candidate is the caller's job, through the real
`layout_*` tool, so the executed-call record that tuning-panel replay depends
on (ADR 0016) always names the call that produced the view. See ADR 0017.
"""

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .layout_quality import QualityReport, evaluate

# Evaluation budget by node count: every candidate is a full layout run.
_BUDGET_BY_SIZE = ((300, 10), (1000, 6), (3000, 4))
_BUDGET_LARGE = 2
# Wall-clock cap for the whole search, in seconds.
TIME_CAP_SECONDS = 60.0

# Metric changes smaller than these are not worth mentioning in a trade-off.
_NOTICEABLE = {
    "node_overlap": 0.02,
    "crossings_per_edge": 0.1,
    "edge_length_cv": 0.05,
    "core_extent": 0.05,
    "aspect": 0.2,
}
# Direction in which each metric improves.
_BETTER = {
    "node_overlap": -1,
    "crossings_per_edge": -1,
    "edge_length_cv": -1,
    "core_extent": +1,
    "aspect": -1,
}
_PHRASES = {
    "node_overlap": "overlap",
    "crossings_per_edge": "crossings",
    "edge_length_cv": "edge-length unevenness",
    "core_extent": "use of space",
    "aspect": "stretch",
}


@dataclass
class Candidate:
    params: Dict[str, Any]
    changes: Dict[str, Tuple[Any, Any]]
    report: QualityReport
    seconds: float


@dataclass
class SearchResult:
    baseline: Candidate
    candidates: List[Candidate] = field(default_factory=list)
    evaluations: int = 0
    stopped_early: bool = False


def evaluation_budget(node_count: int) -> int:
    for limit, budget in _BUDGET_BY_SIZE:
        if node_count <= limit:
            return budget
    return _BUDGET_LARGE


def search(
    G,
    spec,
    base_params: Dict[str, Any],
    sizes,
    tuned_params: Optional[Dict[str, Any]] = None,
    budget: Optional[int] = None,
    time_cap: float = TIME_CAP_SECONDS,
    clock: Callable[[], float] = time.perf_counter,
) -> SearchResult:
    """Score `base_params` and the knob moves that address its issues.

    Args:
        G: The graph as the layout reads it (see `layout.build_layout_graph`).
        spec: The layout's `LayoutSpec`.
        base_params: Parameters of the current layout (networkx kwargs).
        sizes: Drawn node sizes, as `layout_quality.evaluate` takes them.
        tuned_params: The layout's own defaults; relative knob ranges scale
            from these. Defaults to `base_params`.
        budget: Maximum number of layout runs, baseline included.
        time_cap: Stop starting new runs after this many seconds.
    """
    tuned_params = tuned_params or base_params
    budget = budget or evaluation_budget(G.number_of_nodes())
    started = clock()

    def run(params, changes) -> Candidate:
        t0 = clock()
        pos = spec.compute(G, dict(params))
        seconds = clock() - t0
        return Candidate(params, changes, evaluate(pos, G.edges, sizes), seconds)

    baseline = run(base_params, {})
    result = SearchResult(baseline=baseline, evaluations=1)
    seen = {_key(base_params)}

    def within_budget() -> bool:
        if result.evaluations >= budget:
            return False
        # Do not start a run that would likely overshoot the cap.
        elapsed = clock() - started
        return elapsed + baseline.seconds <= time_cap

    def try_params(params, changes) -> Optional[Candidate]:
        key = _key(params)
        if key in seen:
            return None
        if not within_budget():
            result.stopped_early = True
            return None
        seen.add(key)
        candidate = run(params, changes)
        result.evaluations += 1
        result.candidates.append(candidate)
        return candidate

    # Round 1: one step on every knob that addresses a detected issue. With no
    # issue, explore both directions so the caller still has alternatives.
    moves = _moves(spec.knobs, baseline.report.issues, base_params, tuned_params)
    for knob, direction in moves:
        params, changes = _step(knob, direction, base_params, tuned_params)
        if changes:
            try_params(params, changes)

    # Round 2: push the best improvement further, and combine the two best.
    improving = sorted(
        (c for c in result.candidates if c.report.score < baseline.report.score),
        key=lambda c: c.report.score,
    )
    if improving:
        best = improving[0]
        for knob, direction in _moves_of(best, spec.knobs, moves):
            params, changes = _step(knob, direction, best.params, tuned_params)
            if changes:
                try_params(params, {**best.changes, **_rebase(changes, best, base_params)})
        if len(improving) > 1:
            params = {**best.params}
            changes = dict(best.changes)
            for param, (_before, after) in improving[1].changes.items():
                if param not in changes:
                    params[param] = after
                    changes[param] = (base_params.get(param), after)
            try_params(params, changes)

    result.candidates.sort(key=lambda c: c.report.score)
    return result


def tradeoff(candidate: Candidate, baseline: Candidate) -> str:
    """One line naming what got better and what got worse, in plain words."""
    better, worse = [], []
    new, old = candidate.report, baseline.report
    for metric, threshold in _NOTICEABLE.items():
        before, after = getattr(old, metric), getattr(new, metric)
        if before is None or after is None:
            continue
        delta = after - before
        if abs(delta) < threshold:
            continue
        (better if delta * _BETTER[metric] > 0 else worse).append(_PHRASES[metric])
    parts = []
    if better:
        parts.append("better " + ", ".join(better))
    if worse:
        parts.append("worse " + ", ".join(worse))
    return "; ".join(parts) or "about the same"


def metric_deltas(candidate: Candidate, baseline: Candidate) -> Dict[str, float]:
    deltas = {}
    for metric in _NOTICEABLE:
        before = getattr(baseline.report, metric)
        after = getattr(candidate.report, metric)
        if before is not None and after is not None:
            deltas[metric] = round(after - before, 3)
    return deltas


# --- moves --------------------------------------------------------------------


def _moves(knobs, issues, base_params, tuned_params):
    """(knob, direction) pairs to try, most damaging issue first."""
    moves = []
    for issue in issues:
        for knob in knobs:
            if issue not in knob.fixes:
                continue
            direction = knob.fixes[issue]
            for d in ((direction,) if direction else (+1, -1)):
                if knob.toggle and d < 0 and not base_params.get(knob.param):
                    continue
                if (knob, d) not in moves:
                    moves.append((knob, d))
    if not moves:
        for knob in knobs:
            if knob.toggle:
                moves.append((knob, -1 if base_params.get(knob.param) else +1))
            else:
                moves.extend([(knob, +1), (knob, -1)])
    return moves


def _moves_of(candidate: Candidate, knobs, moves):
    """Repeat the moves that produced `candidate` (toggles cannot repeat)."""
    moved = set(candidate.changes)
    return [(k, d) for k, d in moves if k.param in moved and not k.toggle]


def _rebase(changes, best: Candidate, base_params):
    """Report a further step as a change from the original, not from `best`."""
    return {p: (base_params.get(p), after) for p, (_b, after) in changes.items()}


def _step(knob, direction, params, tuned_params):
    """`params` with `knob` moved one step in `direction`; `({}, {})` if it cannot."""
    current = params.get(knob.param)
    if knob.toggle:
        value = direction > 0
        if bool(current) == value:
            return params, {}
    else:
        low, high = knob.bounds(tuned_params.get(knob.param))
        if current is None:
            current = tuned_params.get(knob.param)
        if current is None:
            # Unset means the networkx default; start from the middle of the range.
            current = math.sqrt(low * high) if knob.log and low > 0 else (low + high) / 2
        if knob.log and current > 0:
            value = current * (2.0 if direction > 0 else 0.5)
        else:
            value = current + direction * (high - low) / 4.0
        value = min(max(value, low), high)
        if knob.integer:
            value = int(round(value))
        if math.isclose(value, current, rel_tol=1e-9):
            return params, {}
    moved = {**params, knob.param: value, **knob.requires}
    changes = {knob.param: (params.get(knob.param), value)}
    for param, required in knob.requires.items():
        if params.get(param) != required:
            changes[param] = (params.get(param), required)
    return moved, changes


def _key(params) -> Tuple:
    return tuple(
        sorted(
            (k, round(v, 9) if isinstance(v, float) else v)
            for k, v in params.items()
            if not isinstance(v, (dict, list))
        )
    )


# --- DB-bound entry point -----------------------------------------------------


def suggest_parameters(
    network_id: int, db, layout_name: Optional[str] = None, max_candidates: int = 3
) -> Dict[str, Any]:
    """Score the current layout and return up to `max_candidates` better ones.

    The baseline is the layout as it was last computed (its stored parameters),
    falling back to the layout's own defaults. Each candidate's `arguments` are
    exactly what to pass to the `layout_<name>` tool to reproduce it.
    """
    from common import models

    from .attributes import get_cached_attribute
    from .layout import BULKY_PARAM_KEYS, build_layout_graph, load_layout_positions
    from .layouts import get_spec
    from .layouts.profile import profile_graph
    from .visualization_builder import display_node_sizes

    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if network is None:
        raise ValueError(f"Network {network_id} not found.")
    layout_name = layout_name or network.last_layout_name
    if not layout_name:
        raise ValueError(
            "No layout has been computed for this network yet; run a layout_* tool "
            "first, or name the layout to evaluate."
        )
    spec = get_spec(layout_name)

    stored = {}
    cached = get_cached_attribute(network_id, f"{spec.name}_x", models.NodeAttribute, db)
    if cached is not None and isinstance(cached.computation_params, dict):
        stored = {
            k: v
            for k, v in cached.computation_params.items()
            if k in spec.params and k not in BULKY_PARAM_KEYS
        }
    # A stored run without `weight` on a weight-reading layout was unweighted
    # on purpose (weights are automatic otherwise), so keep it unweighted.
    requested_weight = stored.get("weight")
    if cached is not None and spec.accepts_weight and "weight" not in stored:
        requested_weight = "none"

    weight_attribute, _note, G, _median = build_layout_graph(
        spec, network_id, db, requested_weight
    )
    tuned, _notes = spec.tuned(G, profile_graph(G, weight_attribute))
    # The layout tool re-resolves weights on its own; only a choice that differs
    # from what it would pick automatically has to be passed back to it.
    weight_argument = None
    if spec.accepts_weight:
        from .layouts import resolve_weight

        automatic, _ = resolve_weight(spec, None, network_id, db)
        if weight_attribute != automatic:
            weight_argument = weight_attribute or "none"
    base = {**tuned, **stored}
    if weight_attribute:
        base["weight"] = weight_attribute
    sizes = display_node_sizes(db, network_id)

    if not spec.knobs:
        pos = load_layout_positions(network_id, spec.name, db)
        if not pos:
            raise ValueError(
                f"No stored '{spec.name}' layout for network {network_id}; run "
                f"layout_{spec.name} first."
            )
        report = evaluate(pos, G.edges, sizes)
        return {
            "layout": spec.name,
            "applicable": False,
            "message": (
                f"'{spec.name}' has no parameters that change readability; its "
                "quality is shown for reference. A force-directed layout "
                "(forceatlas2, spring, arf) can be tuned."
            ),
            "current": report.as_dict(),
        }

    result = search(G, spec, base, sizes, tuned_params=tuned)
    baseline = result.baseline
    better = [c for c in result.candidates if c.report.score < baseline.report.score]
    chosen = better[:max_candidates]
    if len(chosen) < max_candidates:
        # Alternatives that trade one problem for another are still worth offering.
        rest = [c for c in result.candidates if c not in chosen]
        chosen += rest[: max_candidates - len(chosen)]

    return {
        "layout": spec.name,
        "applicable": True,
        "current": {"arguments": _arguments(baseline.params, tuned, weight_argument), **baseline.report.as_dict()},
        "candidates": [
            {
                "rank": i + 1,
                "improves_score": c.report.score < baseline.report.score,
                "arguments": _arguments(c.params, tuned, weight_argument),
                "changes": {p: [before, after] for p, (before, after) in c.changes.items()},
                "tradeoff": tradeoff(c, baseline),
                "metric_deltas": metric_deltas(c, baseline),
                **c.report.as_dict(),
            }
            for i, c in enumerate(chosen)
        ],
        "knobs": [k.describe(tuned.get(k.param)) for k in spec.knobs],
        "layouts_evaluated": result.evaluations,
        "stopped_early": result.stopped_early,
        "next_step": (
            f"To apply a candidate, call layout_{spec.name} with its `arguments`, "
            "then visualization_generate."
        ),
    }


def _arguments(
    params: Dict[str, Any], tuned: Dict[str, Any], weight_argument: Optional[str]
) -> Dict[str, Any]:
    """The tool arguments that reproduce `params`: everything off the defaults.

    `weight` is included only when it differs from the automatic choice (an
    opt-out or another attribute); otherwise the tool applies it on its own.
    """
    args = {"weight": weight_argument} if weight_argument else {}
    for key, value in params.items():
        if key == "weight":
            continue
        if key not in tuned or tuned[key] != value:
            args[key] = round(value, 6) if isinstance(value, float) else value
    if "seed" in params:
        args["seed"] = params["seed"]
    return args
