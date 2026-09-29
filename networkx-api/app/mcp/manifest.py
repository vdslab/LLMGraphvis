"""The MCP tool manifest: every tool's name and parameter names, as a JSON file.

The backend cannot import this service, yet its skills name tools and their
parameters. The manifest lives in `common/`, which both containers mount, so
the backend's skill tests can check those names against the real registry.
`tests/test_tool_manifest.py` fails when the file is stale.

Regenerate from `networkx-api/`:

    python -m app.mcp.manifest
"""

import asyncio
import json
from pathlib import Path

def _common_dir() -> Path:
    """`/app/common` in the container, `<repo>/common` on the host.

    The host checkout also has an empty `networkx-api/common` (the container's
    mount point), so the right directory is the one holding the shared models.
    """
    here = Path(__file__).resolve()
    for root in (here.parents[2], here.parents[3]):
        if (root / "common" / "models.py").exists():
            return root / "common"
    raise FileNotFoundError("common/models.py not found above " + str(here))


MANIFEST_PATH = _common_dir() / "mcp_tools.json"


def build_manifest() -> dict:
    import app.mcp.tools  # noqa: F401  (registers the tools)
    from app.core.mcp import mcp

    tools = asyncio.run(mcp.list_tools())
    return {
        tool.name: sorted((tool.inputSchema or {}).get("properties", {}))
        for tool in sorted(tools, key=lambda t: t.name)
    }


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    MANIFEST_PATH.write_text(render(build_manifest()), encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH}")
