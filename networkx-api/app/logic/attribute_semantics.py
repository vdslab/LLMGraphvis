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
