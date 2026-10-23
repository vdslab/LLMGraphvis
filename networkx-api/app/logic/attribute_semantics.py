"""What an attribute *means*, as opposed to how it is stored.

`data_type` only says which value table holds an attribute ("float" or
"string"). That is not enough to choose an encoding: an integer group code and
a centrality score are both floats, and a person's name and a club are both
strings. Every attribute row therefore also carries:

- `role`: why the attribute exists. Imported data, a computed metric, a
  community label or a layout coordinate.
- `measurement`: how its values compare. This decides which visual channel and
  scale fit.

Derived attributes get both from the computation that wrote them, so they are
exact. Imported attributes get a measurement inferred from their values once,
at import time; it is a best guess and is reported as such.
"""

from typing import Any, Dict, Iterable, Optional, Set

# --- Roles -------------------------------------------------------------------

ROLE_DATA = "data"
ROLE_METRIC = "metric"
ROLE_COMMUNITY = "community"
ROLE_COORDINATE = "coordinate"

ROLES = (ROLE_DATA, ROLE_METRIC, ROLE_COMMUNITY, ROLE_COORDINATE)

# --- Measurements ------------------------------------------------------------

# Unordered groups: colour by category, never by gradient.
CATEGORICAL = "categorical"
# Few distinct whole numbers: may be codes (treat as categories) or counts
# (treat as numbers). Only the name and description can tell.
DISCRETE = "discrete"
# Numbers whose differences matter: gradient, size, width, ranking.
QUANTITATIVE = "quantitative"
# (Nearly) one distinct value per element: identity, good for labels only.
IDENTIFIER = "identifier"
# Long free text: read it, do not encode it.
TEXT = "text"

MEASUREMENTS = (CATEGORICAL, DISCRETE, QUANTITATIVE, IDENTIFIER, TEXT)

# Inference thresholds for imported values.
# At most this many distinct whole numbers still reads as codes or counts.
DISCRETE_MAX_DISTINCT = 20
# A string attribute with at least this share of distinct values names its
# elements rather than grouping them.
IDENTIFIER_MIN_UNIQUE_RATIO = 0.9
# Mean characters above which strings are prose rather than labels.
TEXT_MIN_MEAN_LENGTH = 40

# derived_from prefix ("community:louvain") -> role
_ROLE_BY_SOURCE = {
    "centrality": ROLE_METRIC,
    "community": ROLE_COMMUNITY,
    "layout": ROLE_COORDINATE,
}

_MEASUREMENT_BY_ROLE = {
    ROLE_METRIC: QUANTITATIVE,
    ROLE_COMMUNITY: CATEGORICAL,
    ROLE_COORDINATE: QUANTITATIVE,
}

# Values that say yes/no rather than a number or a name.
_BOOLEAN_STRINGS = {"true", "false", "yes", "no"}


def role_for_source(derived_from: Optional[str]) -> str:
    """Role of a derived attribute from its provenance string."""
    if not derived_from:
        return ROLE_DATA
    return _ROLE_BY_SOURCE.get(derived_from.split(":", 1)[0], ROLE_METRIC)


def measurement_for_role(role: str) -> Optional[str]:
    """The measurement a computation implies, or None for imported data."""
    return _MEASUREMENT_BY_ROLE.get(role)


class MeasurementProfiler:
    """Collects one attribute's values and infers its measurement."""

    def __init__(self) -> None:
        self.count = 0
        self.numeric = True
        self.integral = True
        self.boolean = True
        self.total_length = 0
        self.distinct: Set[Any] = set()

    def add(self, value: Any) -> None:
        if value is None:
            return
        self.count += 1
        is_bool = isinstance(value, bool)
        is_number = isinstance(value, (int, float)) and not is_bool
        if not is_bool and str(value).strip().lower() not in _BOOLEAN_STRINGS:
            self.boolean = False
        if is_number:
            if self.integral and float(value) != int(value):
                self.integral = False
        else:
            self.numeric = False
        text = str(value)
        self.total_length += len(text)
        self.distinct.add(value if is_number else text)

    def result(self) -> Optional[str]:
        if not self.count:
            return None
        distinct = len(self.distinct)
        if self.boolean:
            return CATEGORICAL
        if self.numeric:
            if self.integral and distinct <= DISCRETE_MAX_DISTINCT:
                return DISCRETE
            return QUANTITATIVE
        if self.total_length / self.count > TEXT_MIN_MEAN_LENGTH:
            return TEXT
        if self.count > DISCRETE_MAX_DISTINCT and (
            distinct / self.count >= IDENTIFIER_MIN_UNIQUE_RATIO
        ):
            return IDENTIFIER
        return CATEGORICAL


def infer_measurement(values: Iterable[Any]) -> Optional[str]:
    """Measurement of a column of imported values; None when it has no values."""
    profiler = MeasurementProfiler()
    for value in values:
        profiler.add(value)
    return profiler.result()


# --- Descriptions of computed values (ADR 0036) -------------------------------

# derived_from -> how to read its values. The tool docstrings say the same, but
# a tool definition is often not loaded in the turn that later uses the values;
# the attribute listing is. Parameters themselves are listed beside it, so only
# what they change about the reading is added below.
_DERIVED_DESCRIPTIONS = {
    "centrality:degree": (
        "Share of the other nodes each node is linked to (0-1); higher means "
        "more direct contacts."
    ),
    "centrality:in_degree": (
        "Share of the other nodes that link to each node (0-1); higher means "
        "more incoming edges."
    ),
    "centrality:out_degree": (
        "Share of the other nodes each node links to (0-1); higher means more "
        "outgoing edges."
    ),
    "centrality:betweenness": (
        "Share of shortest paths between other nodes that pass through each "
        "node; higher means more of a bridge between parts of the network."
    ),
    "centrality:closeness": (
        "Inverse of the average shortest-path distance from each node to the "
        "nodes it can reach; higher means closer to everyone else."
    ),
    "centrality:eigenvector": (
        "High when a node is linked to other high-scoring nodes; values only "
        "compare within this network."
    ),
    "centrality:pagerank": (
        "Share of time a random walk spends at each node (values sum to 1); "
        "higher means more, and better-linked, edges lead to it."
    ),
    "centrality:clustering": (
        "Share of each node's neighbour pairs that are themselves linked (0-1), "
        "ignoring weights; higher means a tighter local group."
    ),
    "community:louvain": (
        "Community label from Louvain modularity optimisation. Labels are "
        "arbitrary names: nodes with the same label are in one community, and "
        "the numbers have no order or size."
    ),
    "community:greedy_modularity": (
        "Community label from greedy modularity merging. Labels are arbitrary "
        "names: nodes with the same label are in one community, and the numbers "
        "have no order or size."
    ),
    "community:label_propagation": (
        "Community label from label propagation, ignoring weights. Labels are "
        "arbitrary names: nodes with the same label are in one community, and "
        "the numbers have no order or size."
    ),
}

# Readings that replace the default when the run did not normalize.
_UNNORMALIZED_DESCRIPTIONS = {
    "centrality:degree": "Number of edges at each node (not normalized).",
    "centrality:in_degree": "Number of incoming edges at each node (not normalized).",
    "centrality:out_degree": "Number of outgoing edges at each node (not normalized).",
    "centrality:betweenness": (
        "Number of shortest paths between other nodes that pass through each "
        "node (not normalized); higher means more of a bridge."
    ),
}

# How a computation reads an edge weight. Only the sources listed here take one.
_DISTANCE = "distance"
_STRENGTH = "strength"
_WEIGHT_READING = {
    "centrality:betweenness": _DISTANCE,
    "centrality:closeness": _DISTANCE,
    "centrality:eigenvector": _STRENGTH,
    "centrality:pagerank": _STRENGTH,
    "community:louvain": _STRENGTH,
    "community:greedy_modularity": _STRENGTH,
}


def _weight_clause(source: str, params: Dict[str, Any]) -> Optional[str]:
    reading = _WEIGHT_READING.get(source)
    # Rows computed before the weight was recorded say nothing either way.
    if reading is None or "weight" not in params:
        return None
    weight = params.get("weight")
    if not weight:
        return "Edges were treated as unweighted."
    if reading == _DISTANCE:
        return (
            f"Edge attribute '{weight}' was read as a distance: a heavier edge "
            f"is a longer, weaker link."
        )
    return (
        f"Edge attribute '{weight}' was read as tie strength: a heavier edge "
        f"counts more."
    )


def describe_derived(
    derived_from: Optional[str], params: Optional[Dict[str, Any]]
) -> Optional[str]:
    """How to read the values a computation wrote, or None for an unknown source.

    Built from the provenance string and the parameters the run used, so a
    rerun with other parameters gets a matching description. An unknown source
    gets None rather than a guess.
    """
    if not derived_from:
        return None
    params = params or {}
    if derived_from.startswith("layout:"):
        layout = derived_from.split(":", 1)[1]
        return (
            f"Position from the {layout} layout. Only distances between nodes in "
            f"this layout mean anything; it is not a property of the node."
        )
    text = _DERIVED_DESCRIPTIONS.get(derived_from)
    if text is None:
        return None
    if params.get("normalized") is False:
        text = _UNNORMALIZED_DESCRIPTIONS.get(derived_from, text)
    clauses = [text]
    weight = _weight_clause(derived_from, params)
    if weight:
        clauses.append(weight)
    if derived_from == "centrality:betweenness" and params.get("k"):
        clauses.append(
            f"Estimated from {params['k']} sampled nodes, so small differences "
            f"are noise."
        )
    return " ".join(clauses)


# --- Encoding fit ------------------------------------------------------------

_NUMERIC_SCALES = {"LINEAR", "RANKING"}


def encoding_note(
    attribute: Optional[str],
    measurement: Optional[str],
    channel: str,
    scale_type: Optional[str] = None,
) -> Optional[str]:
    """A warning when a channel's scale does not fit the attribute's measurement.

    `channel` is "color", "size" or "width". Returns None when the pairing is
    fine or cannot be judged (unknown measurement, discrete values).
    """
    if not attribute or not measurement or measurement == DISCRETE:
        return None
    scale = (scale_type or "").upper()
    numeric_channel = channel in ("size", "width") or scale in _NUMERIC_SCALES
    if numeric_channel and measurement in (CATEGORICAL, IDENTIFIER, TEXT):
        what = f"{channel} with scale_type={scale}" if scale else channel
        return (
            f"'{attribute}' is {measurement}: its values have no numeric order, "
            f"so mapping it to {what} implies an order that is not in the data. "
            f"Use colour with scale_type='CATEGORICAL' instead, unless the user "
            f"asked for this."
        )
    if scale == "CATEGORICAL" and measurement == QUANTITATIVE:
        return (
            f"'{attribute}' is quantitative: colouring it with CATEGORICAL gives "
            f"every distinct value its own unrelated colour. Use LINEAR (or "
            f"RANKING) unless the user asked for this."
        )
    return None


# Cache-key entries that repeat the provenance string or describe the cache
# itself rather than the computation.
_BOOKKEEPING_PARAMS = {
    "algorithm",
    "centrality_type",
    "layout_name",
    "weight_normalization",
    "init_from_layout",
}


def summarize_parameters(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The scalar parameters a computation ran with, for display.

    Drops bookkeeping keys, unset (None) values and per-node digests: a reader
    needs "resolution=1.0", not the cache key.
    """
    return {
        key: value
        for key, value in (params or {}).items()
        if key not in _BOOKKEEPING_PARAMS
        and isinstance(value, (str, int, float, bool))
        and not (isinstance(value, str) and value.startswith("digest:"))
    }
