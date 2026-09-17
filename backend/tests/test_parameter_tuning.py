"""Parameter tuning sessions shared by the agent's words and the panel (ADR 0016)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app import schemas
from app.api.v1.endpoints.chat import (
    apply_parameter_tuning,
    get_parameter_tuning,
    process_message,
)
from app.services.llm import hooks, inputs, local_tools, tuning
from app.services.llm.engine import GraphVisAgent
from app.services.llm.hooks.builtin.context_blocks import inject_active_tuning
from app.services.llm.hooks.builtin.tuning import expose_tuning_offer
from app.services.llm.providers.types import StreamChunk, ToolDefinition
from app.services.llm.tool_catalog import ToolCatalog
from common import models

LOUVAIN = "analysis_louvain_communities"
COLOR = "visualization_set_node_color"
FA2 = "layout_forceatlas2"

TOOLS = [
    ToolDefinition(
        name=LOUVAIN,
        description="",
        parameters={
            "type": "object",
            "properties": {
                "network_id": {"type": "integer"},
                "resolution": {
                    "type": "number",
                    "default": 1.0,
                    "description": "Below 1 favors larger communities.",
                },
                "seed": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": 42},
                "max_level": {
                    "anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}],
                    "default": None,
                },
            },
        },
    ),
    ToolDefinition(
        name=COLOR,
        description="",
        parameters={
            "type": "object",
            "properties": {
                "network_id": {"type": "integer"},
                "attribute": {"type": "string"},
                "palette": {"type": "string", "enum": ["tableau10", "set2", "paired"]},
            },
        },
    ),
    ToolDefinition(
        name=FA2,
        description="",
        parameters={
            "type": "object",
            "properties": {
                "network_id": {"type": "integer"},
                "scaling_ratio": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                "gravity": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            },
        },
    ),
    ToolDefinition(
        name="subgraph_k_core",
        description="",
        parameters={"type": "object", "properties": {"k": {"type": "integer"}}},
    ),
]

PAYLOAD = {"nodes": [{"id": "a"}], "links": []}


@pytest.fixture
def chat(db):
    user = models.User(username="tuning-test", hashed_password="unused")
    network = models.Network(name="test")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="test", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    return chat


def _turn(chat, *calls):
    state = {"network_id": chat.network_id}
    catalog = ToolCatalog(TOOLS + local_tools.get_local_tools())
    catalog.initialize_turn(state)
    catalog.activate([name for name, _, _ in calls], state)
    state["executed_calls"] = [
        {"name": name, "args": {"network_id": chat.network_id, **args}, "status": status}
        for name, args, status in calls
    ]
    return state


def _louvain_turn(chat, resolution=1.0):
    return _turn(
        chat,
        (LOUVAIN, {"resolution": resolution}, "completed"),
        (COLOR, {"attribute": "louvain_community"}, "completed"),
    )


def _form(**field_overrides):
    field = {
        "tool": LOUVAIN,
        "argument": "resolution",
        "kind": "slider",
        "minimum": 0.2,
        "maximum": 3.0,
        "step": 0.1,
        "suggested": 1.5,
        "rationale": "密度が高いので少し細かめが見やすい",
        "low_label": "大きなまとまり",
        "high_label": "細かく分ける",
    }
    field.update(field_overrides)
    return {"question": "コミュニティの粒度", "tools": [LOUVAIN, COLOR], "fields": [field]}


def _offer(db, chat, form=None, state=None):
    state = state or _louvain_turn(chat)
    return tuning.present_tuning(chat.id, db, form or _form(), state), state


# --- offering a panel --------------------------------------------------------


def test_offer_uses_effective_arguments_schema_description_and_suggestion(db, chat):
    state = _turn(
        chat,
        (LOUVAIN, {"resolution": 0.9}, "failed"),
        (LOUVAIN, {"resolution": 1.0, "seed": 7}, "completed"),
        (COLOR, {"attribute": "louvain_community"}, "completed"),
    )
    result, state = _offer(db, chat, state=state)
    panel = result["parameter_tuning"]

    assert panel["steps"][0]["arguments"] == {
        "network_id": chat.network_id,
        "resolution": 1.0,
        "seed": 7,
    }
    field = panel["fields"][0]
    assert field["id"] == f"{LOUVAIN}.resolution"
    assert field["description"] == "Below 1 favors larger communities."
    assert panel["values"] == {f"{LOUVAIN}.resolution": 1.0}
    assert panel["suggested_values"] == {f"{LOUVAIN}.resolution": 1.5}
    assert "apply_parameter_tuning" in state["enabled_tool_names"]


def test_offer_never_executes_the_suggestion(db, chat):
    with patch(
        "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
    ) as remote:
        _offer(db, chat)
    remote.assert_not_called()


@pytest.mark.parametrize(
    "form, message",
    [
        (_form(argument="gamma"), "has no argument 'gamma'"),
        (_form(minimum=0.0), None),  # below the tool's bound only if declared
        (_form(maximum=0.5), "outside"),
        (_form(suggested=9.0), "suggested"),
        (_form(suggested=1.55), "suggested"),
        ({**_form(), "tools": [LOUVAIN, COLOR, FA2]}, "has not run successfully"),
        (
            {**_form(), "tools": ["subgraph_k_core"], "fields": [
                {"tool": "subgraph_k_core", "argument": "k", "kind": "number"}
            ]},
            "cannot be re-run",
        ),
        (_form(tool=COLOR, argument="attribute"), "not numeric"),
        (_form(tool=LOUVAIN, argument="max_level", minimum=1, maximum=5, step=0.5,
               suggested=None), "whole"),
    ],
)
def test_offer_rejects_what_cannot_be_rerun_faithfully(db, chat, form, message):
    result, _ = _offer(db, chat, form=form)
    if message is None:
        assert "parameter_tuning" in result
        return
    assert message in result["error"]
    assert db.query(models.ParameterTuning).count() == 0


def test_automatic_default_needs_a_suggestion(db, chat):
    state = _turn(chat, (FA2, {}, "completed"))
    form = {
        "question": "広がり",
        "tools": [FA2],
        "fields": [
            {"tool": FA2, "argument": "scaling_ratio", "kind": "slider",
             "minimum": 1, "maximum": 50},
        ],
    }
    result = tuning.present_tuning(chat.id, db, form, state)
    assert "automatic default" in result["error"]

    form["fields"][0]["suggested"] = 4.0
    panel = tuning.present_tuning(chat.id, db, form, state)["parameter_tuning"]
    assert panel["values"] == {f"{FA2}.scaling_ratio": 4.0}


def test_new_panel_supersedes_and_network_change_expires(db, chat):
    first = _offer(db, chat)[0]["parameter_tuning"]
    second = _offer(db, chat)[0]["parameter_tuning"]
    assert db.get(models.ParameterTuning, first["id"]).status == "superseded"

    other = models.Network(name="other")
    db.add(other)
    db.flush()
    row = db.get(models.ParameterTuning, second["id"])
    assert tuning.serialize_tuning(row, other.id)["status"] == "expired"


# --- applying -----------------------------------------------------------------


def _remote(*results):
    return patch(
        "app.services.llm.mcp_client.execute_tool",
        new_callable=AsyncMock,
        side_effect=list(results),
    )


@pytest.mark.asyncio
async def test_form_apply_reruns_pipeline_draws_and_records_history(db, chat):
    panel = _offer(db, chat)[0]["parameter_tuning"]
    row = db.get(models.ParameterTuning, panel["id"])
    queue = AsyncMock()

    with _remote({"content": "Saved."}, {"message": "colored"}, PAYLOAD) as remote:
        outcome = await tuning.apply(
            db, row, {f"{LOUVAIN}.resolution": 2.0},
            source="form", active_network_id=chat.network_id, queue=queue,
        )

    calls = [(c.args[0], c.args[1]) for c in remote.call_args_list]
    assert calls[0] == (LOUVAIN, {"network_id": chat.network_id, "resolution": 2.0})
    assert calls[1][0] == COLOR
    assert calls[2] == ("visualization_generate", {"network_id": chat.network_id})
    queue.put.assert_awaited_once()
    assert outcome["changes"] == [
        {"param": f"{LOUVAIN}.resolution", "before": 1.0, "after": 2.0}
    ]
    db.expire_all()
    row = db.get(models.ParameterTuning, panel["id"])
    assert row.values == {f"{LOUVAIN}.resolution": 2.0}
    assert row.history[-1]["source"] == "form"
    assert row.reported_at is None
    assert db.get(models.Chat, chat.id).visualization_state == PAYLOAD


@pytest.mark.asyncio
async def test_agent_changes_several_parameters_including_non_fields_at_once(db, chat):
    form = _form()
    form["fields"].append(
        {"tool": COLOR, "argument": "palette", "kind": "select",
         "options": ["tableau10", "set2"]}
    )
    state = _turn(
        chat,
        (LOUVAIN, {"resolution": 1.0}, "completed"),
        (COLOR, {"attribute": "louvain_community", "palette": "tableau10"}, "completed"),
    )
    panel = tuning.present_tuning(chat.id, db, form, state)["parameter_tuning"]

    with _remote({"content": "Saved."}, PAYLOAD) as remote:
        result = await tuning.apply_from_agent(
            chat.id, db,
            {"changes": [
                {"param": f"{LOUVAIN}.resolution", "value": 0.6},
                {"param": f"{LOUVAIN}.seed", "value": 7},
                {"param": f"{COLOR}.palette", "value": "set2"},
            ]},
            state,
        )

    assert remote.await_count == 2  # one pipeline run, payload came from the last step
    assert remote.call_args_list[0].args[1]["seed"] == 7
    assert {c["param"] for c in result["changes"]} == {
        f"{LOUVAIN}.resolution", f"{LOUVAIN}.seed", f"{COLOR}.palette",
    }
    db.expire_all()
    row = db.get(models.ParameterTuning, panel["id"])
    assert row.steps[0]["arguments"]["seed"] == 7  # kept for later changes
    assert row.history[-1]["source"] == "agent"
    assert row.reported_at is not None


@pytest.mark.asyncio
async def test_partial_change_keeps_other_values(db, chat):
    form = _form()
    form["fields"].append(
        {"tool": LOUVAIN, "argument": "max_level", "kind": "number",
         "minimum": 1, "maximum": 10, "suggested": 3}
    )
    panel = _offer(db, chat, form=form)[0]["parameter_tuning"]
    row = db.get(models.ParameterTuning, panel["id"])
    with _remote({"content": "ok"}, PAYLOAD):
        await tuning.apply(
            db, row, {f"{LOUVAIN}.resolution": 0.5},
            source="form", active_network_id=chat.network_id,
        )
    assert row.values[f"{LOUVAIN}.max_level"] == 3
    assert row.steps[0]["arguments"]["resolution"] == 0.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes, source, error",
    [
        ({f"{LOUVAIN}.resolution": 5.0}, "form", "outside"),
        ({f"{LOUVAIN}.resolution": 1.05}, "form", "outside"),
        ({f"{LOUVAIN}.seed": 3}, "form", "not a field"),
        ({f"{FA2}.gravity": 3}, "agent", "not part of this pipeline"),
        ({f"{LOUVAIN}.network_id": 3}, "agent", "cannot be tuned"),
    ],
)
async def test_apply_rejects_invalid_changes(db, chat, changes, source, error):
    panel = _offer(db, chat)[0]["parameter_tuning"]
    row = db.get(models.ParameterTuning, panel["id"])
    with _remote() as remote, pytest.raises(tuning.TuningError, match=error):
        await tuning.apply(
            db, row, changes, source=source, active_network_id=chat.network_id
        )
    remote.assert_not_called()


@pytest.mark.asyncio
async def test_agent_rejects_arguments_the_tool_does_not_have(db, chat):
    _, state = _offer(db, chat)
    with _remote() as remote:
        result = await tuning.apply_from_agent(
            chat.id, db, {"changes": [{"param": f"{LOUVAIN}.gamma", "value": 1}]}, state
        )
    assert "has no argument 'gamma'" in result["error"]
    remote.assert_not_called()


@pytest.mark.asyncio
async def test_failed_step_leaves_state_untouched(db, chat):
    panel = _offer(db, chat)[0]["parameter_tuning"]
    row = db.get(models.ParameterTuning, panel["id"])
    with _remote({"content": "ok"}, {"error": "boom"}):
        with pytest.raises(tuning.TuningExecutionError, match="boom"):
            await tuning.apply(
                db, row, {f"{LOUVAIN}.resolution": 2.0},
                source="form", active_network_id=chat.network_id,
            )
    db.expire_all()
    row = db.get(models.ParameterTuning, panel["id"])
    assert row.values == {f"{LOUVAIN}.resolution": 1.0}
    assert row.history == []


@pytest.mark.asyncio
async def test_agent_without_active_panel_is_told_to_rerun_directly(db, chat):
    result = await tuning.apply_from_agent(
        chat.id, db, {"changes": [{"param": f"{LOUVAIN}.resolution", "value": 2}]},
        _louvain_turn(chat),
    )
    assert "No active tuning panel" in result["error"]


# --- API ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_form_endpoint_applies_and_rejects_non_fields(db, chat):
    panel = _offer(db, chat)[0]["parameter_tuning"]
    user = db.get(models.User, chat.user_id)
    with _remote({"content": "ok"}, PAYLOAD), patch(
        "app.services.llm.get_event_queue", new_callable=AsyncMock
    ):
        response = await apply_parameter_tuning(
            chat.id, panel["id"],
            schemas.TuningApplyRequest(values={f"{LOUVAIN}.resolution": 1.8}),
            user, db,
        )
    assert response["visualization"] == PAYLOAD
    assert response["tuning"]["values"] == {f"{LOUVAIN}.resolution": 1.8}
    assert get_parameter_tuning(chat.id, panel["id"], user, db)["values"] == {
        f"{LOUVAIN}.resolution": 1.8
    }

    with patch("app.services.llm.get_event_queue", new_callable=AsyncMock):
        with pytest.raises(HTTPException) as error:
            await apply_parameter_tuning(
                chat.id, panel["id"],
                schemas.TuningApplyRequest(values={f"{LOUVAIN}.seed": 1}),
                user, db,
            )
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_confirm_resumes_with_the_panel_tools_and_is_idempotent(db, chat):
    panel, state = _offer(db, chat)
    panel = panel["parameter_tuning"]
    user = db.get(models.User, chat.user_id)
    payload = schemas.ChatProcessRequest(
        message={"content": "この値で決定"}, parameter_tuning_id=panel["id"]
    )
    tasks = BackgroundTasks()
    assert await process_message(chat.id, payload, tasks, user, db) == {"status": "accepted"}
    assert tasks.tasks[0].args[2] is True  # resumed_from_input
    message = db.query(models.ChatMessage).one().content
    assert message.startswith("この値で決定")
    assert f"{LOUVAIN}.resolution = 1.0" in message
    assert db.get(models.ParameterTuning, panel["id"]).status == "confirmed"

    restored = inputs.restore_activation(db, chat.id, chat.network_id)
    assert LOUVAIN in restored

    retry = await process_message(chat.id, payload, BackgroundTasks(), user, db)
    assert retry == {"status": "already_accepted"}

    with pytest.raises(tuning.TuningInactive):
        await tuning.apply(
            db, db.get(models.ParameterTuning, panel["id"]),
            {f"{LOUVAIN}.resolution": 2.0},
            source="form", active_network_id=chat.network_id,
        )


# --- hooks and exposure ----------------------------------------------------------


@pytest.mark.asyncio
async def test_context_block_reports_values_and_unreported_panel_changes_once(db, chat):
    panel = _offer(db, chat)[0]["parameter_tuning"]
    row = db.get(models.ParameterTuning, panel["id"])
    with _remote({"content": "ok"}, PAYLOAD):
        await tuning.apply(
            db, row, {f"{LOUVAIN}.resolution": 2.0},
            source="form", active_network_id=chat.network_id,
        )

    def turn_start():
        ctx = hooks.build_context(
            hooks.HookEvent.TURN_START,
            chat_id=chat.id, network_id=chat.network_id, turn_state={}, db=db,
        )
        inject_active_tuning(ctx)
        return "\n".join(ctx.context_additions)

    first = turn_start()
    assert f"{LOUVAIN}.resolution = 2.0; suggested 1.5 (not applied)" in first
    assert "大きなまとまり → 細かく分ける" in first
    assert "applied from the panel" in first
    assert "apply_parameter_tuning" in first
    assert "applied from the panel" not in turn_start()


def test_offer_is_exposed_only_after_a_tunable_tool(db, chat):
    for tool, exposed in [("subgraph_k_core", False), ("skill_load", False), (LOUVAIN, True)]:
        state = _turn(chat)
        ctx = hooks.build_context(
            hooks.HookEvent.POST_TOOL,
            chat_id=chat.id, network_id=chat.network_id, turn_state=state, tool_name=tool,
        )
        expose_tuning_offer(ctx)
        assert ("offer_parameter_tuning" in state["enabled_tool_names"]) is exposed


@pytest.mark.asyncio
async def test_turn_with_active_panel_exposes_apply_tool(db, chat):
    from contextlib import asynccontextmanager

    _offer(db, chat)
    with patch("app.services.llm.engine._create_provider", return_value=MagicMock()):
        agent = GraphVisAgent(db=db)
    exposed = []

    def record(history, tools, system_instruction):
        exposed.append({t.name for t in tools})

        async def stream():
            yield StreamChunk(text="done")

        return stream()

    agent.provider.generate.side_effect = record
    agent.provider.supports_native_thinking = False

    @asynccontextmanager
    async def no_session():
        yield None

    with patch(
        "app.services.llm.mcp_client.get_tools", new_callable=AsyncMock, return_value=TOOLS
    ), patch("app.services.llm.mcp_client.session_scope", no_session):
        await agent.process_turn([], AsyncMock(), chat.id, chat.network_id)

    assert "apply_parameter_tuning" in exposed[0]
    assert "Active Parameter Tuning" in agent.system_instruction


def test_summary_counts_categories_of_the_redrawn_color():
    payload = {
        **PAYLOAD,
        "legend": {"node_color": {
            "type": "categorical", "attribute": "louvain_community",
            "mapping": {"0": "#4e79a7", "1": "#f28e2b", "2": "#e15759"},
        }},
    }
    assert tuning._summarize(payload).endswith("louvain_community: 3 categories")


# --- review fixes: aliases, earlier turns, proactive offer ----------------------


def test_field_accepts_min_max_default_aliases(db, chat):
    form = _form()
    field = form["fields"][0]
    field["min"], field["max"], field["default"] = field.pop("minimum"), field.pop("maximum"), field.pop("suggested")
    panel = _offer(db, chat, form=form)[0]["parameter_tuning"]
    assert panel["fields"][0]["minimum"] == 0.2
    assert panel["suggested_values"] == {f"{LOUVAIN}.resolution": 1.5}


def test_offer_in_a_later_turn_uses_the_earlier_calls(db, chat):
    message = models.ChatMessage(chat_id=chat.id, role="model", content="done")
    db.add(message)
    db.flush()
    db.add_all([
        models.ToolExecution(
            message_id=message.id, tool_name=LOUVAIN, status="completed",
            arguments={"network_id": chat.network_id, "resolution": 0.8},
        ),
        models.ToolExecution(
            message_id=message.id, tool_name=COLOR, status="completed",
            arguments={"attribute": "louvain_community"},
        ),
    ])
    db.commit()

    panel = _offer(db, chat, state=_turn(chat))[0]["parameter_tuning"]

    assert panel["values"] == {f"{LOUVAIN}.resolution": 0.8}
    assert panel["steps"][1]["arguments"] == {
        "attribute": "louvain_community", "network_id": chat.network_id,
    }


def test_offer_ignores_calls_made_on_another_network(db, chat):
    message = models.ChatMessage(chat_id=chat.id, role="model", content="done")
    db.add(message)
    db.flush()
    db.add(models.ToolExecution(
        message_id=message.id, tool_name=LOUVAIN, status="completed",
        arguments={"network_id": chat.network_id + 999, "resolution": 0.8},
    ))
    db.commit()
    result, _ = _offer(db, chat, state=_turn(chat, (COLOR, {"attribute": "x"}, "completed")))
    assert "has not run successfully on the current view" in result["error"]


def _no_calls(chat, db, state, text="6つのコミュニティに色分けしました。"):
    return hooks.build_context(
        hooks.HookEvent.NO_TOOL_CALLS,
        chat_id=chat.id, network_id=chat.network_id, turn_state=state, db=db,
        assistant_text=text,
    )


def test_nudge_offers_a_panel_once_after_a_sensitive_result(db, chat):
    from app.services.llm.hooks.builtin.tuning import nudge_tuning_offer

    state = _louvain_turn(chat)
    ctx = _no_calls(chat, db, state)
    nudge_tuning_offer(ctx)
    prompt = state["continuation"]["prompt"]
    assert "offer_parameter_tuning" in prompt
    assert f"['{LOUVAIN}', '{COLOR}']" in prompt
    assert state["continuation"]["model_text"] == ctx.assistant_text

    state["continuation"] = None
    state["continuations_granted"] = 0
    nudge_tuning_offer(_no_calls(chat, db, state))
    assert state["continuation"] is None


@pytest.mark.parametrize(
    "calls, text, active",
    [
        ([(COLOR, {"attribute": "x"}, "completed")], "done", False),
        ([(LOUVAIN, {}, "completed"), ("offer_parameter_tuning", {}, "failed")], "done", False),
        ([(LOUVAIN, {}, "completed")], "", False),
        ([(LOUVAIN, {}, "completed")], "done", True),
    ],
)
def test_nudge_stays_quiet_when_a_panel_is_not_the_missing_piece(db, chat, calls, text, active):
    from app.services.llm.hooks.builtin.tuning import nudge_tuning_offer

    if active:
        _offer(db, chat)
    state = _turn(chat, *calls)
    nudge_tuning_offer(_no_calls(chat, db, state, text))
    assert not state.get("continuation")


def test_tuning_request_about_an_earlier_view_exposes_the_offer(db, chat):
    message = models.ChatMessage(chat_id=chat.id, role="model", content="done")
    db.add(message)
    db.flush()
    for name, args in [
        (LOUVAIN, {"network_id": chat.network_id}),
        (COLOR, {"attribute": "louvain_community"}),
        ("skill_load", {"name": "x"}),
    ]:
        db.add(models.ToolExecution(
            message_id=message.id, tool_name=name, status="completed", arguments=args,
        ))
    db.commit()

    def turn_start(text):
        state = {}
        ctx = hooks.build_context(
            hooks.HookEvent.TURN_START, chat_id=chat.id, network_id=chat.network_id,
            turn_state=state, db=db, user_text=text,
        )
        inject_active_tuning(ctx)
        return state, "\n".join(ctx.context_additions)

    state, block = turn_start("コミュニティの粒度をパラメーターで調整できるようにして")
    assert state["tuning_tools"] == {"offer_parameter_tuning", LOUVAIN, COLOR}
    assert f"tools=['{LOUVAIN}', '{COLOR}']" in block

    state, block = turn_start("中心性を計算して")
    assert "tuning_tools" not in state and block == ""
