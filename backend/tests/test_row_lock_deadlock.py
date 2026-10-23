"""The 2026-10-23 freeze, replayed against a real Postgres (ADR 0038).

A tuning panel is applied (its layout tool is still running) when the user
sends a message to the same chat. Before the fix the apply request held the
chat and panel row locks across the tool await, and `/process` waited for them
on the event loop, so neither could ever finish and the whole process froze.

Row locks do not exist in SQLite, so this runs only with TEST_POSTGRES_URL set
to a disposable database, e.g.
`postgresql+psycopg2://postgres:postgres@db:5432/graphvis_test`.
"""

import asyncio
import faulthandler
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.services.llm import tuning
from common import models
from common.models import Base

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="needs TEST_POSTGRES_URL (row locks need Postgres)"
)

LOUVAIN = "analysis_louvain_communities"
PAYLOAD = {"nodes": [{"id": "a"}], "links": []}


@pytest.fixture
def pg_sessions():
    engine = create_engine(POSTGRES_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed(sessions):
    db = sessions()
    user = models.User(username="deadlock", hashed_password="unused")
    network = models.Network(name="test")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="test", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.flush()
    row = models.ParameterTuning(
        id="panel",
        chat_id=chat.id,
        network_id=network.id,
        specification={
            "question": "q",
            "fields": [
                {
                    "id": f"{LOUVAIN}.resolution",
                    "tool": LOUVAIN,
                    "argument": "resolution",
                    "kind": "number",
                }
            ],
        },
        steps=[{"tool": LOUVAIN, "arguments": {"network_id": network.id}}],
        values={f"{LOUVAIN}.resolution": 1.0},
        initial_values={f"{LOUVAIN}.resolution": 1.0},
        suggested_values={},
        history=[],
        status="active",
        activated_tools=[],
    )
    db.add(row)
    db.commit()
    ids = user.id, chat.id
    db.close()
    return ids


@pytest.mark.asyncio
async def test_message_during_a_running_tuning_apply_does_not_freeze(pg_sessions):
    user_id, chat_id = _seed(pg_sessions)

    def override_db():
        db = pg_sessions()
        try:
            yield db
        finally:
            db.close()

    def override_user():
        db = pg_sessions()
        try:
            return db.get(models.User, user_id)
        finally:
            db.close()

    tool_started, release_tool = asyncio.Event(), asyncio.Event()

    async def slow_layout(tool, arguments, session=None):
        tool_started.set()
        await release_tool.wait()
        return PAYLOAD

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    # A frozen event loop cannot time itself out; a thread can.
    faulthandler.dump_traceback_later(60, exit=True)
    try:
        with (
            patch("app.services.llm.mcp_client.execute_tool", side_effect=slow_layout),
            patch(
                "app.services.chat_service.handle_process_background", new=AsyncMock()
            ),
            patch("app.services.llm.get_event_queue", new_callable=AsyncMock),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                applying = asyncio.create_task(
                    client.post(
                        f"/chat/{chat_id}/tunings/panel/apply",
                        json={"values": {f"{LOUVAIN}.resolution": 2.0}},
                    )
                )
                await asyncio.wait_for(tool_started.wait(), 10)

                sent = await asyncio.wait_for(
                    client.post(
                        f"/chat/{chat_id}/process",
                        json={"message": {"content": "hello"}},
                    ),
                    10,
                )
                assert sent.status_code == 202

                release_tool.set()
                applied = await asyncio.wait_for(applying, 10)
                assert applied.status_code == 200, applied.text
    finally:
        faulthandler.cancel_dump_traceback_later()
        app.dependency_overrides.clear()
        tuning._apply_locks.clear()

    db = pg_sessions()
    try:
        row = db.get(models.ParameterTuning, "panel")
        assert row.values == {f"{LOUVAIN}.resolution": 2.0}
        assert db.query(models.ChatMessage).filter_by(chat_id=chat_id).count() == 1
    finally:
        db.close()
