"""Per-layout definitions, one module per family (mirroring `mcp/tools/layout/`).

Importing this package registers every layout. `logic/layout.py` orchestrates
(graph build, weighting, cache, persistence) and never branches on a layout name.
"""

# Importing each family module is what populates SPECS.
from . import force_directed, geometric, mathematical, structural  # noqa: F401
from .base import (  # noqa: F401
    SPECS,
    LayoutSpec,
    WeightRole,
    canonical_name,
    get_spec,
    layout_names,
    param_keys,
    register,
)
from .weights import OPT_OUT as WEIGHT_OPT_OUT  # noqa: F401
from .weights import resolve_weight  # noqa: F401

__all__ = [
    "SPECS",
    "LayoutSpec",
    "WeightRole",
    "canonical_name",
    "get_spec",
    "layout_names",
    "param_keys",
    "register",
    "resolve_weight",
    "WEIGHT_OPT_OUT",
]
