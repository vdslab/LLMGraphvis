"""Token usage: normalization, cost, persistence and reports (ADR 0025)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.services import usage_report
from app.services.llm import usage as llm_usage
from app.services.llm.pricing import estimate_cost_usd
from app.services.llm.providers.google_genai import usage_from_metadata
from app.services.llm.providers.types import TurnUsage, UsageData

from common import models


def test_gemini_thinking_counts_as_output():
    """`candidates_token_count` excludes thinking, which is billed as output."""
    usage = usage_from_metadata(
        SimpleNamespace(
            prompt_token_count=1000,
            cached_content_token_count=400,
            candidates_token_count=50,
            thoughts_token_count=300,
            tool_use_prompt_token_count=None,
        )
    )
    assert usage.input_tokens == 1000
    assert usage.cached_input_tokens == 400
    assert usage.output_tokens == 350
    assert usage.reasoning_tokens == 300


def test_gemini_missing_counts_are_zero():
    usage = usage_from_metadata(SimpleNamespace(prompt_token_count=10))
    assert usage == UsageData(input_tokens=10)


def test_cost_uses_one_formula_for_every_provider():
    # claude-opus-4-8: input 5, cached 0.5, cache_write 6.25, output 25 per 1M.
    usage = UsageData(
        input_tokens=1_510_000,
        cached_input_tokens=500_000,
        cache_write_tokens=1_000_000,
        output_tokens=100_000,
    )
    cost = estimate_cost_usd("claude-opus-4-8", usage, provider="anthropic")
    assert cost == pytest.approx(0.01 * 5 + 0.5 * 0.5 + 1.0 * 6.25 + 0.1 * 25)

    # gemini-3.8-flash: input 0.75, cached 0.075, output 3.75; no cache writes.
    usage = UsageData(
        input_tokens=1_000_000, cached_input_tokens=400_000, output_tokens=1_000_000
    )
    cost = estimate_cost_usd("gemini-3.8-flash", usage, provider="google")
    assert cost == pytest.approx(0.6 * 0.75 + 0.4 * 0.075 + 3.75)


def test_unknown_model_cost_is_unknown_not_free():
    usage = UsageData(input_tokens=10, output_tokens=10)
    assert estimate_cost_usd("no-such-model", usage, provider="google") is None
    assert estimate_cost_usd("any-local-model", usage, provider="lmstudio") == 0.0


def test_turn_usage_keeps_each_call():
    turn = TurnUsage()
    turn.add_call(UsageData(input_tokens=100, output_tokens=10))
    turn.add_call(UsageData(input_tokens=150, output_tokens=20, reasoning_tokens=5))
    assert turn.input_tokens == 250
    assert turn.reasoning_tokens == 5
    assert [c["input_tokens"] for c in turn.calls] == [100, 150]


def _chat(db, username="alice"):
    user = models.User(username=username, hashed_password="x")
    db.add(user)
    db.flush()
    network = models.Network(name="n")
    db.add(network)
    db.flush()
    chat = models.Chat(name=f"{username} chat", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.flush()
    return user, chat


def test_record_usage_attributes_to_chat_owner(db):
    user, chat = _chat(db)
    turn = TurnUsage()
    turn.add_call(UsageData(input_tokens=100, output_tokens=10))
    turn.add_call(UsageData(input_tokens=200, output_tokens=20))

    row = llm_usage.record_usage(
        db, turn, provider="google", model="gemini-3.8-flash", chat_id=chat.id
    )
    db.flush()

    assert row.user_id == user.id
    assert row.message_id is None
    assert row.iteration_count == 2
    assert len(row.calls) == 2
    assert row.estimated_cost_usd > 0


def test_record_usage_skips_empty_usage(db):
    _, chat = _chat(db)
    assert (
        llm_usage.record_usage(
            db,
            UsageData(),
            provider="google",
            model="gemini-3.8-flash",
            chat_id=chat.id,
        )
        is None
    )


def test_reports_total_by_chat_model_and_day(db):
    user, chat = _chat(db)
    _, other_chat = _chat(db, "bob")
    llm_usage.record_usage(
        db,
        UsageData(input_tokens=100, output_tokens=10),
        provider="google",
        model="gemini-3.8-flash",
        chat_id=chat.id,
    )
    llm_usage.record_usage(
        db,
        UsageData(input_tokens=50, output_tokens=5),
        provider="lmstudio",
        model="local",
        chat_id=chat.id,
        purpose=llm_usage.PURPOSE_TITLE,
    )
    llm_usage.record_usage(
        db,
        UsageData(input_tokens=7, output_tokens=1),
        provider="google",
        model="unpriced",
        chat_id=chat.id,
    )
    llm_usage.record_usage(
        db,
        UsageData(input_tokens=999, output_tokens=999),
        provider="google",
        model="gemini-3.8-flash",
        chat_id=other_chat.id,
    )
    db.flush()

    report = usage_report.chat_usage(db, chat.id)
    assert report["totals"]["input_tokens"] == 157
    assert report["totals"]["task_count"] == 3
    assert report["totals"]["unpriced_count"] == 1
    assert [e["purpose"] for e in report["entries"]] == [
        "agent_turn",
        "title",
        "agent_turn",
    ]

    mine = usage_report.user_usage(db, user.id)
    assert mine["totals"]["input_tokens"] == 157
    assert {m["model"] for m in mine["by_model"]} == {
        "gemini-3.8-flash",
        "local",
        "unpriced",
    }
    assert mine["by_chat"][0]["chat_name"] == "alice chat"
    assert sum(d["input_tokens"] for d in mine["by_day"]) == 157

    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert (
        usage_report.user_usage(db, user.id, since=future)["totals"]["task_count"] == 0
    )
