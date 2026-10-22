"""`common/mcp_tools.json` must match the registered MCP tools.

The backend's skill tests read it to check that skills name real tools and
parameters; a stale manifest would let a renamed tool slip past them.
"""

from app.mcp.manifest import MANIFEST_PATH, build_manifest, render


def test_manifest_is_current():
    assert MANIFEST_PATH.exists(), "Run `python -m app.mcp.manifest`"
    assert MANIFEST_PATH.read_text(encoding="utf-8") == render(build_manifest()), (
        "common/mcp_tools.json is stale; run `python -m app.mcp.manifest` "
        "from networkx-api/"
    )
