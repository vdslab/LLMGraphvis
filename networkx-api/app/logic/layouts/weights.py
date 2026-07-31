"""Which edge attribute, if any, a layout should be weighted by.

The rule in one line: **auto-assign only when the answer is unambiguous, and say
so either way**.

A network's imported edge weight (`edges.weight`) is the one weight whose meaning
is known — it is *the* weight of the file the user uploaded — so a layout that
reads weights as strength uses it without being asked. Any other numeric edge
attribute could be a distance, a year, or an id; guessing which one is a
connection strength is the caller's decision, not this module's, so those are
reported as candidates and never chosen automatically.
"""

from app.core.logging import get_logger

from ..utils.graph_builder import WEIGHT_COLUMN, summarize_edge_weights
from .base import WeightRole

logger = get_logger(__name__)

# Values of `weight` that mean "lay this graph out unweighted". Weighted is the
# default for strength layouts, so this is the only way to ask for the opposite.
OPT_OUT = {"", "none", "no", "off", "false", "unweighted"}


def _alternatives_clause(summary, verb: str) -> str:
    """Name the other numeric edge attributes, so a caller can pick one."""
    names = summary.get("alternatives") or []
    if not names:
        return ""
    listed = ", ".join(f"'{n}'" for n in names)
    return f" Other numeric edge attributes {verb}: {listed}."


def resolve_weight(spec, requested, network_id: int, db):
    """Decide the weight for one layout run.

    Returns `(weight_attribute, note)`. The note is not decoration: "weighted by
    default" would be just another silent behaviour — the mirror image of the bug
    it replaces — unless every run reports what it did and what else was
    available. It is appended to the tool's return message, so the model reads it
    and can offer the alternative.
    """
    requested_name = requested.strip() if isinstance(requested, str) else requested

    if spec.weight_role is WeightRole.NONE:
        if requested_name:
            logger.warning(
                f"Layout '{spec.name}' has no weight concept; ignoring "
                f"weight={requested_name!r}."
            )
        return None, ""

    if isinstance(requested_name, str) and requested_name.lower() in OPT_OUT:
        return None, "Edge weights were ignored, as requested."

    if requested_name:
        # An explicit name wins outright, including a name that is not the
        # imported weight. build_graph_from_db raises if it does not exist, so a
        # typo surfaces as an error rather than as a silently unweighted layout.
        return requested_name, f"Weighted by the '{requested_name}' edge attribute."

    summary = summarize_edge_weights(network_id, db)

    if spec.weight_role is WeightRole.DISTANCE:
        # Never automatic: here a weight is the target distance between two
        # endpoints, so applying a strength-like weight would draw the most
        # strongly connected nodes furthest apart.
        if summary["is_informative"]:
            return None, (
                f"Computed unweighted: this layout reads a weight as the target "
                f"distance between endpoints (heavier = further apart), so it is "
                f"never applied automatically. The imported edge weights "
                f"(range {_span(summary)}) can be used that way with "
                f"weight='{WEIGHT_COLUMN}'."
                + _alternatives_clause(summary, "could be used instead")
            )
        return None, _alternatives_clause(
            summary, "could be used as edge distances"
        ).strip()

    if not summary["is_informative"]:
        # Nothing assignable: no weights, all edges equal, or non-positive values
        # that mean nothing as an attraction strength. Staying unweighted is
        # correct — but if the file carries other numeric edge attributes, one of
        # them may be the strength the user has in mind, so name them.
        return None, _alternatives_clause(
            summary, "could be used as edge strength"
        ).strip()

    logger.info(
        f"Layout '{spec.name}' on network {network_id}: using the imported edge "
        f"weights automatically (range {_span(summary)}, "
        f"{summary['distinct_values']} distinct values)."
    )
    return WEIGHT_COLUMN, (
        f"Edge weights were used automatically as connection strength "
        f"(range {_span(summary)}); pass weight='none' to ignore them."
        + _alternatives_clause(summary, "can be used instead")
    )


def _span(summary) -> str:
    return f"{summary['min']:.3g}–{summary['max']:.3g}"
