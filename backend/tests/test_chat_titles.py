from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app import schemas
from app.api.v1.endpoints.chat import update_chat
from app.services import chat_service
from app.services.llm import titles
from app.services.llm.providers.types import StreamChunk

from common import models

# --- pure helpers ---------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("New Chat", True),
        ("new chat", True),
        ("  New Chat  ", True),
        ("新しいチャット", True),
        ("", True),
        (None, True),
        ("Karate club communities", False),
    ],
)
def test_is_placeholder_name(name, expected):
    assert titles.is_placeholder_name(name) is expected


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("karate_club.graphml", "karate club"),
        ("/tmp/uploads/les_miserables.GraphML", "les miserables"),
        ("network.gml", "network"),
        ("New Chat.graphml", None),
        (".graphml", None),
        (None, None),
    ],
)
def test_name_from_filename(filename, expected):
    assert titles.name_from_filename(filename) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Karate club communities", "Karate club communities"),
        ('"Karate club communities"', "Karate club communities"),
        ("Title: Karate club communities", "Karate club communities"),
        ("「空手クラブの分析」", "空手クラブの分析"),
        ("空手クラブの分析。", "空手クラブの分析"),
        ("First line\nsecond line", "First line"),
        ("   ", None),
        ("New Chat", None),
    ],
)
def test_clean_title(raw, expected):
    assert titles._clean_title(raw) == expected


def test_clean_title_truncates():
    assert len(titles._clean_title("a" * 200)) == titles.MAX_TITLE_LENGTH


# --- generation -----------------------------------------------------------


class _FakeProvider:
    """Minimal LLMProvider stand-in that replays fixed chunks."""

    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate(self, history, tools, system_instruction):
        self.calls.append((history, tools, system_instruction))

        async def _stream():
            yield StreamChunk(text=self.text)

        return _stream()


@pytest.mark.asyncio
async def test_generate_chat_title_uses_provider_reply():
    provider = _FakeProvider("Karate club communities\n")
    with patch("app.services.llm.titles.create_provider", return_value=provider):
        title = await titles.generate_chat_title(
            user_message="コミュニティを検出して色分けして",
            assistant_message="3 communities found.",
            current_name="karate club",
        )

    assert title == "Karate club communities"
    # The title call must never be able to touch the graph.
    _, tools, _ = provider.calls[0]
    assert tools == []
    # The chat's current (filename-derived) name is offered as dataset context.
    prompt = provider.calls[0][0][0].parts[0].text
    assert "karate club" in prompt


@pytest.mark.asyncio
async def test_generate_chat_title_swallows_provider_errors():
    with patch(
        "app.services.llm.titles.create_provider", side_effect=RuntimeError("boom")
    ):
        assert await titles.generate_chat_title("hi", "hello") is None


@pytest.mark.asyncio
async def test_generate_chat_title_ignores_empty_user_message():
    with patch("app.services.llm.titles.create_provider") as factory:
        assert await titles.generate_chat_title("   ", "hello") is None
    factory.assert_not_called()


# --- auto-naming policy ---------------------------------------------------


def _make_chat(db, name="New Chat", name_is_custom=False):
    user = models.User(username=f"u{name_is_custom}{name}", hashed_password="x")
    network = models.Network(name="n")
    db.add_all([user, network])
    db.commit()

    chat = models.Chat(
        name=name,
        user_id=user.id,
        network_id=network.id,
        name_is_custom=name_is_custom,
    )
    db.add(chat)
    db.commit()
    return user, chat


def _add_user_messages(db, chat_id, count):
    for i in range(count):
        db.add(models.ChatMessage(chat_id=chat_id, role="user", content=f"m{i}"))
        db.add(models.ChatMessage(chat_id=chat_id, role="model", content=f"r{i}"))
    db.commit()


@pytest.mark.asyncio
async def test_autoname_renames_after_first_exchange(db):
    _, chat = _make_chat(db)
    _add_user_messages(db, chat.id, 1)

    mock_queue = AsyncMock()
    with patch(
        "app.services.llm.titles.generate_chat_title",
        new_callable=AsyncMock,
        return_value="Karate club communities",
    ), patch(
        "app.services.llm.get_event_queue", new_callable=AsyncMock
    ) as get_queue:
        get_queue.return_value = mock_queue
        await chat_service._maybe_autoname_chat(
            db, chat.id, "分析して", "done", "google", "gemini-2.5-flash"
        )

    db.refresh(chat)
    assert chat.name == "Karate club communities"
    assert chat.name_is_custom is False

    event = mock_queue.put.call_args[0][0]
    assert event["event"] == "chat_renamed"
    assert "Karate club communities" in event["data"]


@pytest.mark.asyncio
async def test_autoname_skips_user_named_chat(db):
    _, chat = _make_chat(db, name="My analysis", name_is_custom=True)
    _add_user_messages(db, chat.id, 1)

    with patch(
        "app.services.llm.titles.generate_chat_title", new_callable=AsyncMock
    ) as generate:
        await chat_service._maybe_autoname_chat(
            db, chat.id, "分析して", "done", "google", "gemini-2.5-flash"
        )

    generate.assert_not_called()
    db.refresh(chat)
    assert chat.name == "My analysis"


@pytest.mark.asyncio
async def test_autoname_runs_only_on_the_first_turn(db):
    _, chat = _make_chat(db, name="karate club")
    _add_user_messages(db, chat.id, 2)

    with patch(
        "app.services.llm.titles.generate_chat_title", new_callable=AsyncMock
    ) as generate:
        await chat_service._maybe_autoname_chat(
            db, chat.id, "次は中心性を見て", "done", "google", "gemini-2.5-flash"
        )

    generate.assert_not_called()
    db.refresh(chat)
    assert chat.name == "karate club"


@pytest.mark.parametrize(
    "initial_name,name_is_custom,expected_name,expect_event",
    [
        ("New Chat", False, "karate club", True),
        ("My analysis", True, "My analysis", False),
    ],
)
@pytest.mark.asyncio
async def test_upload_names_chat_after_the_file(
    initial_name, name_is_custom, expected_name, expect_event
):
    """The uploaded filename becomes the chat's provisional name — unless the
    user has already named the chat themselves."""
    chat_id, network_id = 1, 100

    with patch(
        "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
    ) as mock_exec, patch(
        "app.services.llm.get_event_queue", new_callable=AsyncMock
    ) as mock_get_queue, patch(
        "app.services.llm.context.build_data_overview", new_callable=AsyncMock
    ) as mock_overview, patch(
        "app.core.database.SessionLocal"
    ) as mock_session_cls:
        mock_exec.return_value = {"network_id": network_id, "nodes": [], "links": []}
        mock_overview.return_value = ""
        mock_queue = AsyncMock()
        mock_get_queue.return_value = mock_queue

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_chat = MagicMock()
        mock_chat.id = chat_id
        mock_chat.network_id = network_id
        mock_chat.name = initial_name
        mock_chat.name_is_custom = name_is_custom
        mock_db.query.return_value.filter.return_value.first.return_value = mock_chat

        await chat_service.handle_upload_background(
            chat_id, network_id, "<graphml></graphml>", "karate_club.graphml"
        )

    assert mock_chat.name == expected_name
    events = [call[0][0]["event"] for call in mock_queue.put.call_args_list]
    assert ("chat_renamed" in events) is expect_event


def test_manual_rename_pins_the_name(db):
    user, chat = _make_chat(db)

    update_chat(
        chat_id=chat.id,
        chat_update=schemas.ChatUpdate(name="My analysis"),
        current_user=user,
        db=db,
    )

    db.refresh(chat)
    assert chat.name == "My analysis"
    assert chat.name_is_custom is True


def test_provider_change_does_not_pin_the_name(db):
    user, chat = _make_chat(db)

    update_chat(
        chat_id=chat.id,
        chat_update=schemas.ChatUpdate(provider="anthropic", model="claude-sonnet-5"),
        current_user=user,
        db=db,
    )

    db.refresh(chat)
    assert chat.name_is_custom is False
