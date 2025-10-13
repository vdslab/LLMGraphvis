import pytest


class DummyResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


class DummyAsyncClient:
    def __init__(self, sample_graphml):
        self.sample_graphml = sample_graphml

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, timeout=None):
        # Simulate get_sample_network
        return DummyResponse(200, {"graphml_content": self.sample_graphml})

    async def post(self, url, json=None, timeout=None):
        # Simulate change_layout
        if url.endswith("/tools/change_layout"):
            return DummyResponse(200, {
                "result": {
                    "success": True,
                    "positions": {"1": {"x": 1.0, "y": 2.0}},
                    "graphml_content": self.sample_graphml,
                    "layout_type": json.get("layout_type") if isinstance(json, dict) else "spring"
                }
            })
        # Default success
        return DummyResponse(200, {"result": {"success": True}})


def test_chat_process_triggers_broadcast(client, test_user, test_user_data, sample_graphml, monkeypatch):
    """Post to /chat/process and assert the server broadcasts graph_updated to connected websocket clients."""

    # Obtain JWT token
    resp = client.post(
        "/auth/token",
        data={"username": test_user_data["username"], "password": test_user_data["password"]},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Patch the LLM to request a layout tool call
    async def fake_process_chat_message(history):
        return {
            "tool_calls": [
                {
                    "function": {
                        "name": "change_layout",
                        "arguments": {"layout_type": "spring"}
                    }
                }
            ]
        }

    import services.llm as llmmod
    monkeypatch.setattr(llmmod, "process_chat_message", fake_process_chat_message)

    # Patch httpx.AsyncClient to use our DummyAsyncClient
    import httpx

    def dummy_client_factory(*args, **kwargs):
        return DummyAsyncClient(sample_graphml)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy_client_factory())

    # Connect websocket and post to /chat/process
    headers = {"Authorization": f"Bearer {token}"}

    # Use TestClient's websocket_connect in a thread-safe way
    with client.websocket_connect(f"/ws?token={token}") as websocket:
        # Post the chat message (no conversation_id to force creation)
        post_resp = client.post("/chat/process", json={"message": "Apply spring layout"}, headers=headers)
        assert post_resp.status_code == 200

        # Receive the broadcast
        data = websocket.receive_json()
        assert data.get("event") == "graph_updated"
        assert "network_update" in data
        nu = data["network_update"]
        assert nu.get("type") == "change_layout"
        assert "positions" in nu and isinstance(nu["positions"], dict)
