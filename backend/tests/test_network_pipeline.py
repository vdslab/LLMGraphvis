"""The upload pipeline's REST calls to networkx-api (ADR 0035)."""

import httpx
import pytest

from app.services import network_service


@pytest.fixture
def networkx_api(monkeypatch):
    """Answer networkx-api requests with the handler a test installs."""
    calls = []
    state = {"handler": None}

    def transport_handler(request):
        calls.append(request)
        return state["handler"](request)

    def client():
        return httpx.AsyncClient(
            base_url="http://networkx-api:8001",
            transport=httpx.MockTransport(transport_handler),
        )

    monkeypatch.setattr(network_service, "_networkx_client", client)

    def install(handler):
        state["handler"] = handler
        return calls

    return install


@pytest.mark.asyncio
async def test_import_sends_the_xml_itself_not_json(networkx_api):
    """JSON would escape every quote of a multi-megabyte document."""
    calls = networkx_api(lambda request: httpx.Response(200, json={"network_id": 7}))
    graphml = '<graphml><node id="会議"/></graphml>'

    network_id = await network_service.import_graphml(5, graphml)

    assert network_id == 7
    request = calls[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/networks/5/import"
    assert request.headers["content-type"].startswith("application/xml")
    assert request.content == graphml.encode("utf-8")


@pytest.mark.asyncio
async def test_layout_and_visualization_hit_their_routes(networkx_api):
    calls = networkx_api(
        lambda request: httpx.Response(
            200, json={"network_id": 7, "nodes": [], "layout": "spring"}
        )
    )

    layout_name = await network_service.calculate_initial_layout(7)
    vis = await network_service.build_visualization(7)

    assert layout_name == "spring"
    assert [(c.method, c.url.path) for c in calls] == [
        ("POST", "/api/v1/networks/7/layout/initial"),
        ("GET", "/api/v1/networks/7/visualization"),
    ]
    assert vis["network_id"] == 7


@pytest.mark.asyncio
async def test_a_rejected_step_names_the_route_status_and_detail(networkx_api):
    networkx_api(
        lambda request: httpx.Response(422, json={"detail": "Failed to parse GraphML"})
    )

    with pytest.raises(network_service.NetworkPipelineError) as excinfo:
        await network_service.import_graphml(5, "<broken")

    message = str(excinfo.value)
    assert "/import" in message and "422" in message
    assert "Failed to parse GraphML" in message


@pytest.mark.asyncio
async def test_a_timeout_is_reported_as_a_pipeline_error(networkx_api):
    def stall(request):
        raise httpx.ReadTimeout("stalled", request=request)

    networkx_api(stall)

    with pytest.raises(network_service.NetworkPipelineError, match="did not answer"):
        await network_service.calculate_initial_layout(7)
