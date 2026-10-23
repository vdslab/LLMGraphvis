"""REST routes the upload pipeline uses instead of MCP tools (ADR 0035)."""

from app.api.v1.endpoints import networks
from app.logic import visualization_builder

from common import models

# Above the 4 MiB the MCP transport accepts, which is what stalled an upload.
MCP_BODY_LIMIT = 4 * 1024 * 1024


def _graphml(nodes: int, note_chars: int) -> str:
    note = "講義の概要。" * (note_chars // 6)
    rows = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="note" for="node" attr.name="note" attr.type="string"/>',
        '<graph edgedefault="undirected">',
    ]
    rows += [
        f'<node id="n{i}"><data key="note">{note}</data></node>' for i in range(nodes)
    ]
    rows += [f'<edge source="n{i}" target="n{i + 1}"/>' for i in range(nodes - 1)]
    rows += ["</graph>", "</graphml>"]
    return "\n".join(rows)


def _network(db) -> int:
    network = models.Network(name="Upload")
    db.add(network)
    db.commit()
    return network.id


def test_import_accepts_a_file_larger_than_the_mcp_limit(client, db):
    graphml = _graphml(nodes=700, note_chars=2400)
    assert len(graphml.encode("utf-8")) > MCP_BODY_LIMIT
    network_id = _network(db)

    response = client.post(
        f"/api/v1/networks/{network_id}/import",
        content=graphml.encode("utf-8"),
        headers={"Content-Type": "application/xml; charset=utf-8"},
    )

    assert response.status_code == 200, response.text
    saved_id = response.json()["network_id"]
    assert db.query(models.Node).filter_by(network_id=saved_id).count() == 700


def test_import_refuses_a_file_over_the_upload_cap(client, db, monkeypatch):
    monkeypatch.setattr(networks, "MAX_GRAPHML_SIZE", 100)
    network_id = _network(db)

    response = client.post(
        f"/api/v1/networks/{network_id}/import",
        content=_graphml(nodes=10, note_chars=60).encode("utf-8"),
    )

    assert response.status_code == 413


def test_import_reports_a_broken_file_as_unprocessable(client, db):
    network_id = _network(db)

    response = client.post(
        f"/api/v1/networks/{network_id}/import", content=b"<graphml><graph>"
    )

    assert response.status_code == 422
    assert "GraphML" in response.json()["detail"]


def test_visualization_route_builds_what_the_mcp_tool_builds(client, db):
    """`visualization_generate` is `build_visualization(with_quality=True)`;
    the tool opens its own session, so the builder is compared directly."""
    network_id = _network(db)
    imported = client.post(
        f"/api/v1/networks/{network_id}/import",
        content=_graphml(nodes=12, note_chars=12).encode("utf-8"),
    ).json()["network_id"]
    layout = client.post(
        f"/api/v1/networks/{imported}/layout", json={"layout_name": "forceatlas2"}
    )
    assert layout.status_code == 200, layout.text

    response = client.get(f"/api/v1/networks/{imported}/visualization")

    assert response.status_code == 200, response.text
    via_rest = response.json()
    via_builder = visualization_builder.build_visualization(
        db, imported, with_quality=True
    )
    assert via_rest["network_id"] == imported
    assert {n["id"]: (n["x"], n["y"]) for n in via_rest["nodes"]} == {
        n["id"]: (n["x"], n["y"]) for n in via_builder["nodes"]
    }
    assert via_rest["layout_quality"]["score"] == via_builder["layout_quality"]["score"]


def test_visualization_route_answers_404_for_an_unknown_network(client):
    assert client.get("/api/v1/networks/987654/visualization").status_code == 404
