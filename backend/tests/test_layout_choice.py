"""The question of how to tune a force layout just drawn (ADR 0018)."""

import pytest

from app.services.llm import hooks
from app.services.llm.hooks.builtin.tuning import nudge_layout_choice, nudge_tuning_offer
from common import models

FA2 = "layout_forceatlas2"
SPRING = "layout_spring"
GENERATE = "visualization_generate"


@pytest.fixture
def chat(db):
    user = models.User(username="layout-choice-test", hashed_password="unused")
    network = models.Network(name="test")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="test", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    return chat


def _state(chat, *calls):
    return {
        "network_id": chat.network_id,
        "executed_calls": [
            {"name": name, "args": {"network_id": chat.network_id, **args}, "status": status}
            for name, args, status in calls
        ],
    }


def _ctx(chat, db, state, text="ForceAtlas2 で配置しました。"):
    return hooks.build_context(
        hooks.HookEvent.NO_TOOL_CALLS,
        chat_id=chat.id, network_id=chat.network_id, turn_state=state, db=db,
        assistant_text=text,
    )


def _earlier(db, chat, name, args=None):
    message = models.ChatMessage(chat_id=chat.id, role="model", content="done")
    db.add(message)
    db.flush()
    db.add(models.ToolExecution(
        message_id=message.id, tool_name=name, status="completed",
        arguments=args if args is not None else {"network_id": chat.network_id},
    ))
    db.commit()


def _drawn(layout=FA2, **args):
    return [(layout, args, "completed"), (GENERATE, {}, "completed")]


def test_first_automatic_layout_asks_how_to_tune(db, chat):
    state = _state(chat, *_drawn())
    nudge_layout_choice(_ctx(chat, db, state))
    prompt = state["continuation"]["prompt"]
    assert "ask_user" in prompt and "layout_quality" in prompt
    for option in ("おまかせで調整", "今の値から自分で調整", "このままでよい"):
        assert option in prompt


def test_it_replaces_the_panel_nudge(db, chat):
    state = _state(chat, *_drawn())
    ctx = _ctx(chat, db, state)
    nudge_layout_choice(ctx)
    first = state["continuation"]
    nudge_tuning_offer(ctx)
    assert state["continuation"] is first
    assert state["tuning_nudged"]


def test_asks_only_once_per_turn(db, chat):
    state = _state(chat, *_drawn())
    nudge_layout_choice(_ctx(chat, db, state))
    state["continuation"] = None
    state["continuations_granted"] = 0
    nudge_layout_choice(_ctx(chat, db, state))
    assert state["continuation"] is None


def test_same_algorithm_again_does_not_ask(db, chat):
    _earlier(db, chat, FA2)
    state = _state(chat, *_drawn())
    nudge_layout_choice(_ctx(chat, db, state))
    assert not state.get("continuation")


def test_switching_algorithm_asks_again(db, chat):
    _earlier(db, chat, FA2)
    state = _state(chat, *_drawn(SPRING))
    nudge_layout_choice(_ctx(chat, db, state))
    assert state.get("continuation")


def test_a_layout_on_another_network_does_not_count(db, chat):
    _earlier(db, chat, FA2, {"network_id": chat.network_id + 999})
    state = _state(chat, *_drawn())
    nudge_layout_choice(_ctx(chat, db, state))
    assert state.get("continuation")


def test_evaluation_tools_are_not_a_previous_layout(db, chat):
    _earlier(db, chat, FA2)
    _earlier(db, chat, "layout_suggest_parameters")
    state = _state(chat, *_drawn())
    nudge_layout_choice(_ctx(chat, db, state))
    assert not state.get("continuation")


@pytest.mark.parametrize(
    "calls, text",
    [
        (_drawn(gravity=3.0), "done"),                      # parameters were chosen
        ([(FA2, {}, "completed")], "done"),                 # computed but not drawn
        (_drawn("layout_circular"), "done"),                # no knobs
        (_drawn() + [("layout_suggest_parameters", {}, "completed")], "done"),
        (_drawn() + [("offer_parameter_tuning", {}, "completed")], "done"),
        (_drawn(), ""),                                     # no closing text
    ],
)
def test_stays_quiet(db, chat, calls, text):
    state = _state(chat, *calls)
    nudge_layout_choice(_ctx(chat, db, state, text))
    assert not state.get("continuation")


def test_seed_and_weight_are_still_automatic(db, chat):
    state = _state(chat, *_drawn(seed=42, weight="none"))
    nudge_layout_choice(_ctx(chat, db, state))
    assert state.get("continuation")


def test_an_open_question_is_left_alone(db, chat):
    state = _state(chat, *_drawn())
    state["input_request"] = {"id": "x"}
    nudge_layout_choice(_ctx(chat, db, state))
    assert not state.get("continuation")
