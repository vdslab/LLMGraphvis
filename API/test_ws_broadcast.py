import time
import json
import asyncio

import pytest


def test_ws_broadcast_received(client, test_user, test_user_data):
    """Connect to the /ws endpoint with a valid token, trigger a server-side broadcast, and assert it is received."""
    # Request a token for the created test user
    resp = client.post(
        "/auth/token",
        data={"username": test_user_data["username"], "password": test_user_data["password"]},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Prepare a test route on the app that will schedule a broadcast in the server event loop
    async def _trigger_broadcast():
        message = {
            "event": "graph_updated",
            "network_id": 1,
            "network_update": {"type": "change_layout", "positions": {"1": {"x": 0, "y": 0}}}
        }
        # Await broadcast on the server event loop so TestClient websocket receives it
        await client.app.state.ws_manager.broadcast(message)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("ok")

    # Add the test-only route
    client.app.add_api_route("/_test/broadcast", _trigger_broadcast, methods=["POST"])

    # Start a websocket connection using the TestClient
    with client.websocket_connect(f"/ws?token={token}") as websocket:
        # Trigger the server-side broadcast via the test route
        resp = client.post("/_test/broadcast")
        assert resp.status_code == 200

        # The TestClient websocket receives json; assert we get the broadcast
        data = websocket.receive_json()
        assert data["event"] == "graph_updated"
        assert data["network_id"] == 1
        assert "network_update" in data

import threading
import time
import pytest
import json

from main import app


def test_ws_broadcast_received_by_client(client, auth_headers, test_user):
    """Integration test: a connected WebSocket client receives broadcast messages."""
    # Mock get_current_user_from_token via providing a valid token path in test
    # The auth_headers fixture already obtains a valid token for test_user
    token = auth_headers["Authorization"].split()[1]

    # Connect websocket
    with client.websocket_connect(f"/ws?token={token}") as websocket:
        # Give some time for the server to register the connection
        time.sleep(0.1)

        # Prepare a message to broadcast
        message = {
            "event": "graph_updated",
            "network_id": 1,
            "network_update": {"type": "change_layout", "positions": {"1": {"x": 0.1, "y": 0.2}}}
        }

        # Broadcast from the app's ws_manager in a separate thread (since broadcast is async)
        def do_broadcast():
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            coro = app.state.ws_manager.broadcast(message)
            loop.run_until_complete(coro)
            loop.close()

        thread = threading.Thread(target=do_broadcast)
        thread.start()

        # Receive message on the client side
        data = websocket.receive_json(timeout=2)
        thread.join()

        assert data["event"] == "graph_updated"
        assert data["network_id"] == 1
        assert "network_update" in data
        assert data["network_update"]["type"] == "change_layout"
        assert "positions" in data["network_update"]
