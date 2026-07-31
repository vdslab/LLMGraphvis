"""Tests for the network context/overview text built from MCP resources.

Regression cover for a silent failure: every resource read returned {} (the
server labelled its JSON bodies text/plain, and two resource functions called
logic helpers that had been renamed), so the post-upload message told the user
their graph had no name, no size and no attributes.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from app.services.llm import context, mcp_client

NODE_ATTRS = [
    {"name": "composer", "data_type": "string", "stats": {"top_values": ["Mozart"]}},
    {
        "name": "birthYear",
        "data_type": "float",
        "stats": {"min": 1659.0, "max": 1977.0},
    },
    {"name": "forceatlas2_x", "data_type": "float", "stats": {"min": -1.0, "max": 1.0}},
    {"name": "forceatlas2_y", "data_type": "float", "stats": {"min": -1.0, "max": 1.0}},
]
EDGE_ATTRS = [
    {"name": "weight", "data_type": "float", "stats": {"min": 1.0, "max": 116.0}}
]

METADATA = {"id": 1, "name": "Concerts", "description": "Co-performance network"}
STRUCTURE = {"node_count": 1144, "edge_count": 8608, "density": 0.013}
# Edge weights live on the edge row, not in the edge-attribute listing, so the
# structure resource is the only place they are visible.
WEIGHTS = {
    "edge_count": 8608,
    "weighted_edge_count": 8608,
    "distinct_values": 42,
    "min": 1.0,
    "max": 116.0,
    "is_uniform": False,
    "is_informative": True,
}


def _patch_resources(metadata=METADATA, structure=STRUCTURE, nodes=None, edges=None):
    nodes = NODE_ATTRS if nodes is None else nodes
    edges = EDGE_ATTRS if edges is None else edges
    return patch.object(
        context,
        "_fetch_network_resources",
        new=AsyncMock(return_value=(metadata, structure, nodes, edges)),
    )


@pytest.mark.asyncio
async def test_overview_reports_name_size_and_attributes():
    with _patch_resources():
        overview = await context.build_data_overview(1)

    assert "**Name:** Concerts" in overview
    assert "**Size:** 1144 nodes, 8608 edges" in overview
    assert "**Node attributes (2):** `composer`, `birthYear`" in overview
    assert "**Edge attributes (1):** `weight`" in overview
    assert "none" not in overview


@pytest.mark.asyncio
async def test_overview_stays_short():
    """The overview is a glance before the first message, not a data dictionary."""
    with _patch_resources():
        overview = await context.build_data_overview(1)

    lines = overview.splitlines()
    assert len(lines) <= 8, overview
    assert all(len(line) <= 200 for line in lines), overview
    # Per-attribute types and value ranges belong in the agent's context only.
    assert "(float)" not in overview
    assert "min: 1659" not in overview


@pytest.mark.asyncio
async def test_overview_truncates_multiline_description():
    long_desc = "Co-performance network.\nNode type: musical_work\nSource: yearbook"
    with _patch_resources(metadata={"name": "Concerts", "description": long_desc}):
        overview = await context.build_data_overview(1)

    assert "- **Description:** Co-performance network. …" in overview
    assert "Node type" not in overview


@pytest.mark.asyncio
async def test_overview_caps_the_attribute_name_list():
    many = [{"name": f"attr{i}", "data_type": "float"} for i in range(40)]
    with _patch_resources(nodes=many):
        overview = await context.build_data_overview(1)

    assert "**Node attributes (40):**" in overview
    assert "`attr24`" in overview
    assert "`attr25`" not in overview
    assert "... and 15 more" in overview


@pytest.mark.asyncio
async def test_overview_hides_generated_layout_coordinates():
    """The upload pipeline lays out the graph before this runs; those coordinates
    are not attributes of the file the user uploaded."""
    with _patch_resources():
        overview = await context.build_data_overview(1)

    assert "forceatlas2_x" not in overview
    assert "forceatlas2_y" not in overview


@pytest.mark.asyncio
async def test_overview_distinguishes_unreadable_from_empty():
    with _patch_resources(nodes={}, edges=[]):
        overview = await context.build_data_overview(1)

    assert "**Node attributes:** could not be read" in overview
    assert "**Edge attributes:** none" in overview


@pytest.mark.asyncio
async def test_context_summary_keeps_attribute_types_and_ranges():
    """Only the user-facing overview is trimmed; the agent still gets the detail."""
    with _patch_resources():
        summary = await context.build_context_summary(1)

    assert "- birthYear (float) [min: 1659.00, max: 1977.00]" in summary
    assert "- composer (string) [values: 'Mozart']" in summary


@pytest.mark.asyncio
async def test_overview_is_omitted_when_nothing_can_be_read():
    with _patch_resources(metadata={}, structure={}, nodes={}, edges={}):
        assert await context.build_data_overview(1) == ""


@pytest.mark.asyncio
async def test_context_summary_keeps_layout_coordinates():
    """The agent needs to know which layouts exist, unlike the user-facing overview."""
    with _patch_resources():
        summary = await context.build_context_summary(1)

    assert "Stats: 1144 Nodes, 8608 Edges" in summary
    assert "forceatlas2_x" in summary


@pytest.mark.asyncio
async def test_context_summary_reports_edge_weights():
    """Weights are invisible in the attribute listing, so without this line the
    agent has no way to know the uploaded file was weighted."""
    with _patch_resources(structure={**STRUCTURE, "edge_weights": WEIGHTS}):
        summary = await context.build_context_summary(1)

    assert "Edge weights: present, range 1–116 (42 distinct values)." in summary
    assert "use them automatically" in summary


@pytest.mark.asyncio
async def test_context_summary_stays_silent_about_uniform_weights():
    """All-equal weights change no layout, so mentioning them only invites the
    agent to pass a parameter that does nothing."""
    uniform = {**WEIGHTS, "is_uniform": True, "is_informative": False}
    with _patch_resources(structure={**STRUCTURE, "edge_weights": uniform}):
        summary = await context.build_context_summary(1)

    assert "Edge weights" not in summary


@pytest.mark.asyncio
async def test_overview_reports_the_edge_weight_range():
    with _patch_resources(structure={**STRUCTURE, "edge_weights": WEIGHTS}):
        overview = await context.build_data_overview(1)

    assert "- **Edge weights:** 1–116" in overview


@pytest.mark.asyncio
async def test_context_summary_marks_unreadable_resources():
    with _patch_resources(structure={"error": "boom"}, nodes={"error": "boom"}):
        summary = await context.build_context_summary(1)

    assert "Stats: unavailable" in summary
    assert "Node Attributes: unavailable" in summary


class _FakeSession:
    def __init__(self, text, mime):
        self._contents = SimpleNamespace(text=text, mimeType=mime)

    async def read_resource(self, uri):
        return SimpleNamespace(contents=[self._contents])


@pytest.mark.asyncio
@pytest.mark.parametrize("mime", ["application/json", "text/plain", None])
async def test_resource_json_is_parsed_regardless_of_declared_mime(mime):
    """FastMCP labels a resource text/plain unless the server sets mime_type;
    the body must still be read."""
    session = _FakeSession(json.dumps(STRUCTURE), mime)

    result = await mcp_client.get_resource("network://1/structure", session=session)

    assert result == STRUCTURE


@pytest.mark.asyncio
async def test_resource_non_json_body_yields_empty_dict():
    session = _FakeSession("not json at all", "text/plain")

    assert await mcp_client.get_resource("network://1/structure", session=session) == {}
