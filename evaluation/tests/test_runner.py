import json
from pathlib import Path

from evaluation.runner import REQUIRED_MODEL, temporary_cline_configuration


def test_temporary_cline_configuration_restores_files(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    settings = home / ".cline" / "data" / "settings"
    settings.mkdir(parents=True)
    providers_path = settings / "providers.json"
    mcp_path = settings / "cline_mcp_settings.json"
    providers_original = json.dumps(
        {
            "lastUsedProvider": "vertex",
            "providers": {"lmstudio": {"settings": {"model": REQUIRED_MODEL}}},
        },
        separators=(",", ":"),
    ).encode()
    mcp_original = b'{"mcpServers":{"existing":{"command":"example"}}}'
    providers_path.write_bytes(providers_original)
    mcp_path.write_bytes(mcp_original)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    with temporary_cline_configuration(Path("/python"), {"A": "B"}):
        providers = json.loads(providers_path.read_text())
        servers = json.loads(mcp_path.read_text())["mcpServers"]
        assert providers["lastUsedProvider"] == "lmstudio"
        assert servers["existing"]["disabled"] is True
        assert servers["graphvis-evaluation"]["env"] == {"A": "B"}

    assert providers_path.read_bytes() == providers_original
    assert mcp_path.read_bytes() == mcp_original
