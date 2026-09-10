from app.services.llm.hooks.builtin.intent import (
    nudge_choice_ui,
    retry_empty_response,
)
from app.services.llm.hooks.types import HookContext, HookEvent


def context(text, state=None):
    return HookContext(
        event=HookEvent.NO_TOOL_CALLS,
        chat_id=1,
        network_id=1,
        turn_state=state or {},
        assistant_text=text,
    )


def test_numbered_analysis_suggestions_request_ui_not_execution():
    ctx = context(
        "**1. 属性の比較**\n**2. 中心性**\n**3. コミュニティ**\n"
        "ご希望を教えてください。"
    )
    nudge_choice_ui(ctx)
    prompt = ctx.turn_state["continuation"]["prompt"]
    assert "ask_user" in prompt
    assert "do not execute" in prompt.lower()


def test_explanations_existing_forms_and_repeated_nudges_do_not_reprompt():
    for ctx in [
        context("1. ファイルを選びます。\n2. 読み込みを待ちます。"),
        context("どのような分析ができますか、というご質問に回答しました。"),
        context("1. A\n2. B\n選んでください", {"input_request": {"id": "q"}}),
        context("1. A\n2. B\n選んでください", {"continuations_granted": 1}),
    ]:
        nudge_choice_ui(ctx)
        assert not ctx.turn_state.get("continuation")


def test_empty_provider_response_retries_once_without_claiming_success():
    ctx = context("")
    retry_empty_response(ctx)
    prompt = ctx.turn_state["continuation"]["prompt"]
    assert "latest instruction" in prompt
    assert "Do not claim completion" in prompt

    repeated = context("", {"continuations_granted": 1})
    retry_empty_response(repeated)
    assert not repeated.turn_state.get("continuation")
