from pathlib import Path

from evaluation.surfaces import _tool_source_locations


def test_tool_source_locations_discovers_decorated_tools(tmp_path: Path) -> None:
    source = tmp_path / "new_tool.py"
    source.write_text(
        "from somewhere import mcp\n"
        "@mcp.tool()\n"
        "def visualization_new_tool(value: int):\n"
        "    return value\n",
        encoding="utf-8",
    )

    locations = _tool_source_locations(tmp_path)

    assert locations["visualization_new_tool"] == {
        "path": str(source),
        "line": 3,
    }
