from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app import schemas
from app.api.v1.endpoints.chat import get_analysis_input, process_message
from app.services.llm.engine import GraphVisAgent
from app.services.llm.inputs import InputForm, accept_answer, present_question
from app.services.llm.providers.types import FunctionCallData, StreamChunk
from common import models

FORM = {
    "question": "どの条件で分析しますか？",
    "fields": [
        {
            "id": "method",
            "label": "分析目的",
            "kind": "select",
            "options": ["中心性", "経路"],
        },
        {
            "id": "iterations",
            "label": "反復回数",
            "kind": "slider",
            "minimum": 10,
            "maximum": 100,
            "step": 10,
        },
    ],
}


@pytest.fixture
def chat(db):
    user = models.User(username="input-test", hashed_password="unused")
    network = models.Network(name="test")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="test", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    return chat


def test_form_validates_bounds_options_and_field_ids():
    form = InputForm.model_validate(FORM)
    assert "反復回数: 20" in form.answer_text({"method": "経路", "iterations": 20})
    for values in [
        {"method": "invalid", "iterations": 20},
        {"method": "経路", "iterations": 21},
        {"method": "経路", "iterations": True},
        {"method": "経路", "iterations": float("inf")},
        {"method": "経路"},
    ]:
        with pytest.raises(ValueError):
            form.answer_text(values)


def test_form_normalizes_model_generated_title_alias():
    title_only = {
        "question": "Choose",
        "fields": [
            {
                "id": "goal",
                "title": "Analysis goal",
                "kind": "select",
                "options": ["Centrality", "Community", "Attributes"],
            }
        ],
    }
    assert InputForm.model_validate(title_only).fields[0].label == "Analysis goal"

    redundant_title = {
        **title_only,
        "fields": [
            {
                **title_only["fields"][0],
                "label": "目的",
                "title": "Long redundant title",
            }
        ],
    }
    assert InputForm.model_validate(redundant_title).fields[0].label == "目的"


def test_form_merges_split_single_option_select_fields():
    # Japanese case (matches the exact real-world scenario from chat 221)
    split_form_ja = {
        "question": "対立する2つのグループをどのような視点から分析しますか？",
        "fields": [
            {
                "id": "goal_1_centrality",
                "label": "仲介者を見る",
                "kind": "select",
                "options": ["クラブ所属で色分けし、媒介中心性でサイズを決定するビュー。"],
            },
            {
                "id": "goal_2_community",
                "label": "コミュニティ検出",
                "kind": "select",
                "options": ["Louvain法でコミュニティを検出し、色分けするビュー。"],
            },
            {
                "id": "goal_3_pagerank",
                "label": "影響力を測る",
                "kind": "select",
                "options": ["PageRankで重要度を計算し、サイズで示すビュー。"],
            },
        ],
    }
    validated_ja = InputForm.model_validate(split_form_ja)
    assert len(validated_ja.fields) == 1
    assert validated_ja.fields[0].kind == "select"
    assert validated_ja.fields[0].label == "分析目的"
    assert len(validated_ja.fields[0].options) == 3
    assert "Louvain法" in validated_ja.fields[0].options[1]

    # English case
    split_form_en = {
        "question": "Which perspective would you like to explore?",
        "fields": [
            {"id": "opt_1", "label": "Option 1", "kind": "select", "options": ["View A"]},
            {"id": "opt_2", "label": "Option 2", "kind": "select", "options": ["View B"]},
        ],
    }
    validated_en = InputForm.model_validate(split_form_en)
    assert len(validated_en.fields) == 1
    assert validated_en.fields[0].label == "Analysis goal"
    assert validated_en.fields[0].options == ["View A", "View B"]

    # Legitimate multiple fields (select + slider) must not be merged
    mixed_form = {
        "question": "Parameters",
        "fields": [
            {"id": "method", "label": "Method", "kind": "select", "options": ["A", "B"]},
            {"id": "param", "label": "Param", "kind": "slider", "minimum": 1, "maximum": 10},
        ],
    }
    validated_mixed = InputForm.model_validate(mixed_form)
    assert len(validated_mixed.fields) == 2


def test_form_auto_heals_malformed_fields_inputs():
    # Real-world chat 226 case: XML tag prefix leaked into fields string
    xml_string_payload = {
        "question": "どの可視化を作成しますか？（各選択肢の内容は上の説明をご覧ください）",
        "fields": (
            '\n<parameter name="fields">[{"id": "analysis_goal", "label": "可視化のゴール", '
            '"kind": "select", "options": ["対立と橋渡し役を同時に表示", "接点リンクを強調", "構造を比較"]}]'
        ),
    }
    validated_xml = InputForm.model_validate(xml_string_payload)
    assert len(validated_xml.fields) == 1
    assert validated_xml.fields[0].id == "analysis_goal"
    assert validated_xml.fields[0].label == "可視化のゴール"
    assert len(validated_xml.fields[0].options) == 3

    # Flattened payload case: field attributes passed at top level with residual XML tag
    flattened_payload = {
        "question": "どの条件で分析しますか？",
        "fields": '\n<parameter name="id">analysis_goal',
        "label": "可視化の方針",
        "kind": "select",
        "options": ["①clubで2陣営を色分け", "②接点リンク強調"],
    }
    validated_flattened = InputForm.model_validate(flattened_payload)
    assert len(validated_flattened.fields) == 1
    assert validated_flattened.fields[0].id == "analysis_goal"
    assert validated_flattened.fields[0].label == "可視化の方針"
    assert len(validated_flattened.fields[0].options) == 2

    # Single dictionary payload
    dict_payload = {
        "question": "Choose a view",
        "fields": {
            "id": "goal",
            "label": "Analysis goal",
            "kind": "select",
            "options": ["View 1", "View 2"],
        },
    }
    validated_dict = InputForm.model_validate(dict_payload)
    assert len(validated_dict.fields) == 1
    assert validated_dict.fields[0].id == "goal"
    assert len(validated_dict.fields[0].options) == 2

    # Field containing residual XML tags in string values
    residual_xml_payload = {
        "question": "Choose a view",
        "fields": [
            {
                "id": '<parameter name="id">goal</parameter>',
                "label": "<title>Goal Selection</title>",
                "kind": "select",
                "options": ["Option A", "Option B"],
            }
        ],
    }
    validated_residual = InputForm.model_validate(residual_xml_payload)
    assert validated_residual.fields[0].id == "goal"
    assert validated_residual.fields[0].label == "Goal Selection"


def test_question_survives_reload_and_supersedes_previous(db, chat):
    state = {}
    first = present_question(chat.id, db, FORM, state)["input_request"]
    assert state["input_request"]["id"] == first["id"]
    second = present_question(chat.id, db, FORM, {})["input_request"]
    db.expire_all()
    assert db.get(models.AnalysisInput, first["id"]).status == "superseded"
    assert db.get(models.AnalysisInput, second["id"]).status == "pending"
    with pytest.raises(ValueError, match="no longer active"):
        accept_answer(chat, db, first["id"], None, "経路で")


@pytest.mark.asyncio
async def test_answer_submission_is_idempotent_and_bound_to_chat(db, chat):
    request = present_question(chat.id, db, FORM, {})["input_request"]
    user = db.get(models.User, chat.user_id)
    payload = schemas.ChatProcessRequest(
        message={"content": "ignored"},
        input_request_id=request["id"],
        input_values={"method": "経路", "iterations": 20},
    )
    tasks = BackgroundTasks()
    assert await process_message(chat.id, payload, tasks, user, db) == {
        "status": "accepted"
    }
    assert len(tasks.tasks) == 1
    retry_tasks = BackgroundTasks()
    assert await process_message(chat.id, payload, retry_tasks, user, db) == {
        "status": "already_accepted"
    }
    assert not retry_tasks.tasks
    assert db.query(models.ChatMessage).count() == 1
    assert "分析目的: 経路" in db.query(models.ChatMessage).one().content
    assert get_analysis_input(chat.id, request["id"], user, db)["status"] == "answered"
    other_user = models.User(username="other", hashed_password="unused")
    db.add(other_user)
    db.commit()
    with pytest.raises(HTTPException) as error:
        get_analysis_input(chat.id, request["id"], other_user, db)
    assert error.value.status_code == 404


def test_network_change_expires_question(db, chat):
    request = present_question(chat.id, db, FORM, {})["input_request"]
    network = models.Network(name="other")
    db.add(network)
    db.flush()
    chat.network_id = network.id
    db.commit()
    with pytest.raises(ValueError, match="no longer active"):
        accept_answer(chat, db, request["id"], None, "yes")


@pytest.mark.asyncio
async def test_plain_text_reply_resolves_pending_question(db, chat):
    request = present_question(chat.id, db, FORM, {})["input_request"]
    user = db.get(models.User, chat.user_id)
    payload = schemas.ChatProcessRequest(message={"content": "まず経路だけ調べて"})
    await process_message(chat.id, payload, BackgroundTasks(), user, db)
    assert db.get(models.AnalysisInput, request["id"]).answer == {
        "free_text": "まず経路だけ調べて"
    }


@pytest.mark.asyncio
async def test_question_blocks_entire_tool_batch_and_ends_generation(db, chat):
    with patch("app.services.llm.engine._create_provider", return_value=MagicMock()):
        agent = GraphVisAgent(db=db)
    state = {"network_id": chat.network_id}
    queue = AsyncMock()
    calls = [
        FunctionCallData(name="analysis_pagerank", args={}),
        FunctionCallData(name="ask_user", args=FORM),
        FunctionCallData(name="visualization_generate", args={}),
    ]

    async def stream():
        # The explanation rides along with the form: a bare form is deferred by
        # `guard_question_needs_prose`, so it cannot stand in for this case.
        yield StreamChunk(
            text="このデータでは club 属性が使えます。", function_calls=calls
        )

    with patch(
        "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
    ) as remote:
        text, log, _ = await agent._execute_tool_loop(
            stream(), [], [], queue, chat.id, chat.network_id, None, state
        )
    remote.assert_not_called()
    agent.provider.generate.assert_not_called()
    assert '::tool-execution{index="0"}' in text
    assert FORM["question"] not in text
    assert [call["name"] for call in log[0]["tool_calls"]] == ["ask_user"]
    assert db.query(models.AnalysisInput).count() == 1


def test_other_is_explicit_validated_and_readable():
    form = InputForm.model_validate(FORM)
    assert "Other: 二つのクラブを比較" in form.answer_text(
        {
            "method": {"other": "二つのクラブを比較"},
            "iterations": 20,
        }
    )
    for custom in [
        {"other": " "},
        {"other": "x", "unexpected": 1},
        {"other": "x" * 4001},
    ]:
        with pytest.raises(ValueError):
            form.answer_text({"method": custom, "iterations": 20})
    form.fields[0].allow_other = False
    with pytest.raises(ValueError):
        form.answer_text({"method": {"other": "比較"}, "iterations": 20})


def test_other_answer_persists_and_duplicate_submission_is_idempotent(db, chat):
    question = present_question(chat.id, db, FORM, {})["input_request"]
    values = {"method": {"other": "club別に比較したい"}, "iterations": 20}
    text = accept_answer(chat, db, question["id"], values, "")
    db.commit()
    assert "club別に比較したい" in text
    assert accept_answer(chat, db, question["id"], values, "") is None
    stored = db.get(models.AnalysisInput, question["id"])
    assert stored.answer == values


def test_multiselect_can_combine_candidates_with_one_custom_answer():
    form = InputForm(
        question="比較",
        fields=[
            {
                "id": "metrics",
                "kind": "multiselect",
                "label": "指標",
                "options": ["次数", "媒介"],
            }
        ],
    )
    assert "次数, Other: 三角形" in form.answer_text(
        {"metrics": ["次数", {"other": "三角形"}]}
    )
    for values in [
        ["次数", "次数"],
        [{"other": "x"}, {"other": "y"}],
        [{"other": ""}],
        ["unknown"],
    ]:
        with pytest.raises(ValueError):
            form.answer_text({"metrics": values})
