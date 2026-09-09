"""NetworkX upgrades must account for every native layout parameter."""

import inspect
from unittest.mock import patch

import networkx as nx
import pytest
from app.logic.layout import calculate_layout
from app.logic.layouts import SPECS
from app.mcp.tools import layout as tools
from test_layout_parameters import setup_graph

# Intentional application contracts, not accidentally missing parameters.
NATIVE_EXCEPTIONS = {
    "dim": "The canvas and persistent coordinates are 2D.",
    "store_pos_as": "Coordinates are persisted as <layout>_x and <layout>_y.",
}


def test_every_native_layout_parameter_is_public_or_explained():
    for name, spec in SPECS.items():
        native = set(inspect.signature(getattr(nx, f"{name}_layout")).parameters)
        native -= {"G", "backend", "backend_kwargs"}
        assert native - spec.params <= NATIVE_EXCEPTIONS.keys(), name
        tool = getattr(tools, f"layout_{name}")
        assert spec.params <= set(inspect.signature(tool).parameters), name
        assert "dim=2" in tool.__doc__ and "store_pos_as" in tool.__doc__


def test_explicit_null_seed_reaches_networkx(db):
    setup_graph(db)
    with patch("networkx.spring_layout", wraps=nx.spring_layout) as compute:
        calculate_layout(1, "spring", db, overrides={"seed": None})
    assert compute.call_args.kwargs["seed"] is None


def test_explicit_layers_reach_networkx(db):
    setup_graph(db)
    groups = {"left": ["n0", "n1", "n2"], "right": ["n3", "n4", "n5"]}
    result = calculate_layout(1, "multipartite", db, overrides={"subset_key": groups})
    assert result["attributes"] == ["multipartite_x", "multipartite_y"]
    with pytest.raises(ValueError, match="exactly once"):
        calculate_layout(
            1, "multipartite", db, overrides={"subset_key": {"only": ["n0"]}}
        )
