"""Tests for the safety guards, normalizers, and intent detection.

These cover the behaviour that used to live only as prose in the system prompt.
The point of moving it into hooks is that a model cannot skip it, so the tests
assert on refusal, not on advice.
"""

import pytest
from app.services.llm.hooks.builtin import guards, intent, normalize
from app.services.llm.hooks.types import HookContext, HookEvent, new_turn_state


class FakeDB:
    """Minimal stand-in for the read-only lookups `dbinfo` performs.

    The guards only ever read attribute names and node/edge counts, so the tests
    inject those directly through `turn_state` memo keys rather than building a
    SQLAlchemy session.
    """


def ctx(
    tool_name,
    args=None,
    *,
    node_attrs=None,
    edge_attrs=None,
    size=None,
    network_id=7,
    turn_state=None,
    event=HookEvent.PRE_TOOL,
    **kw,
):
    state = turn_state if turn_state is not None else new_turn_state(10)
    state["network_id"] = network_id
    if node_attrs is not None:
        state[f"_attrs_node_{network_id}"] = node_attrs
    if edge_attrs is not None:
        state[f"_attrs_edge_{network_id}"] = edge_attrs
    if size is not None:
        state[f"_size_{network_id}"] = size
    return HookContext(
        event=event,
        chat_id=1,
        network_id=network_id,
        turn_state=state,
        db=FakeDB(),
        tool_name=tool_name,
        args=dict(args or {}),
        **kw,
    )


# --------------------------------------------------------------------------
# normalize_network_id
# --------------------------------------------------------------------------


class TestNormalizeNetworkId:
    def test_injects_missing_network_id(self):
        c = ctx("layout_spring", {})
        decision = normalize.normalize_network_id(c)
        assert decision.action == "modify"
        assert decision.args["network_id"] == 7

    def test_leaves_explicit_network_id_alone(self):
        c = ctx("layout_spring", {"network_id": 99})
        assert normalize.normalize_network_id(c) is None

    def test_injection_is_silent(self):
        """Plumbing, not a correction — reporting it on every call is noise."""
        assert normalize.normalize_network_id(ctx("layout_spring", {})).reason is None

    def test_no_op_without_a_network(self):
        c = ctx("layout_spring", {}, network_id=0)
        c.turn_state["network_id"] = None
        c.network_id = 0
        assert normalize.normalize_network_id(c) is None


# --------------------------------------------------------------------------
# normalize_attribute_case
# --------------------------------------------------------------------------


class TestNormalizeAttributeCase:
    def test_corrects_case_only_difference(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "Club"},
            node_attrs=["club", "degree_centrality"],
        )
        decision = normalize.normalize_attribute_case(c)
        assert decision.action == "modify"
        assert decision.args["attribute"] == "club"
        assert "club" in decision.reason

    def test_exact_match_is_untouched(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "club"},
            node_attrs=["club"],
        )
        assert normalize.normalize_attribute_case(c) is None

    def test_does_not_guess_at_a_different_word(self):
        """'Nationality' -> 'citizenship' is not a correction anyone can infer."""
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "Nationality"},
            node_attrs=["citizenship"],
        )
        assert normalize.normalize_attribute_case(c) is None

    def test_ambiguous_case_match_is_left_for_the_guard(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "type"},
            node_attrs=["Type", "TYPE"],
        )
        assert normalize.normalize_attribute_case(c) is None

    def test_edge_tools_check_edge_attributes(self):
        c = ctx(
            "visualization_set_edge_color",
            {"attribute": "Weight"},
            node_attrs=["club"],
            edge_attrs=["weight"],
        )
        decision = normalize.normalize_attribute_case(c)
        assert decision.args["attribute"] == "weight"

    def test_tools_without_an_attribute_argument_are_ignored(self):
        c = ctx("layout_spring", {"k": 1.0}, node_attrs=["club"])
        assert normalize.normalize_attribute_case(c) is None

    def test_no_known_attributes_means_no_opinion(self):
        """Missing information is not evidence the attribute is wrong."""
        c = ctx("visualization_set_node_color", {"attribute": "club"}, node_attrs=[])
        assert normalize.normalize_attribute_case(c) is None


# --------------------------------------------------------------------------
# normalize_numeric_params
# --------------------------------------------------------------------------


class TestNormalizeNumericParams:
    def test_clamps_negative_iterations(self):
        decision = normalize.normalize_numeric_params(
            ctx("layout_spring", {"iterations": -5})
        )
        assert decision.args["iterations"] == 1
        assert "clamped" in decision.reason

    def test_clamps_damping_factor_below_one(self):
        """PageRank diverges at damping_factor >= 1."""
        decision = normalize.normalize_numeric_params(
            ctx("analysis_pagerank", {"damping_factor": 1.5})
        )
        assert decision.args["damping_factor"] == 0.999

    def test_in_range_values_untouched(self):
        assert (
            normalize.normalize_numeric_params(
                ctx("layout_spring", {"iterations": 500, "k": 0.5})
            )
            is None
        )

    def test_preserves_int_type(self):
        decision = normalize.normalize_numeric_params(
            ctx("layout_forceatlas2", {"max_iter": 10**9})
        )
        assert isinstance(decision.args["max_iter"], int)

    def test_k_means_different_things_per_tool(self):
        """spring's k is a float distance; betweenness's k is a pivot count."""
        spring = normalize.normalize_numeric_params(
            ctx("layout_spring", {"k": 0.5})
        )
        assert spring is None  # 0.5 is a valid distance

        betweenness = normalize.normalize_numeric_params(
            ctx("analysis_betweenness_centrality", {"k": 0.5})
        )
        assert betweenness.args["k"] == 1  # but not a valid sample count

    def test_booleans_are_not_treated_as_numbers(self):
        assert (
            normalize.normalize_numeric_params(
                ctx("layout_forceatlas2", {"linlog": True})
            )
            is None
        )

    def test_unknown_params_are_ignored(self):
        assert (
            normalize.normalize_numeric_params(
                ctx("layout_spring", {"something_else": -999})
            )
            is None
        )


# --------------------------------------------------------------------------
# guard_attribute_exists
# --------------------------------------------------------------------------


class TestGuardAttributeExists:
    def test_denies_unknown_attribute_and_lists_the_real_ones(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "nonexistent"},
            node_attrs=["club", "degree_centrality"],
        )
        decision = guards.guard_attribute_exists(c)
        assert decision.action == "deny"
        assert "club" in decision.reason
        assert "degree_centrality" in decision.reason

    def test_allows_a_known_attribute(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "club"},
            node_attrs=["club"],
        )
        assert guards.guard_attribute_exists(c) is None

    def test_denies_ambiguous_case_match_and_says_to_ask(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "type"},
            node_attrs=["Type", "TYPE"],
        )
        decision = guards.guard_attribute_exists(c)
        assert decision.action == "deny"
        assert "more than one" in decision.reason
        assert "Ask the user" in decision.reason

    def test_metric_argument_gets_a_compute_first_hint(self):
        c = ctx(
            "node_get_top_ranked",
            {"metric": "pagerank"},
            node_attrs=["club"],
        )
        decision = guards.guard_attribute_exists(c)
        assert decision.action == "deny"
        assert "analysis_" in decision.reason

    def test_candidate_list_is_truncated(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "zzz"},
            node_attrs=[f"attr_{i:03d}" for i in range(100)],
        )
        decision = guards.guard_attribute_exists(c)
        assert "more)" in decision.reason

    def test_no_attributes_known_means_no_block(self):
        c = ctx("visualization_set_node_color", {"attribute": "club"}, node_attrs=[])
        assert guards.guard_attribute_exists(c) is None


# --------------------------------------------------------------------------
# guard_expensive_computation
# --------------------------------------------------------------------------


class TestGuardExpensiveComputation:
    def test_denies_betweenness_on_a_large_graph(self):
        c = ctx("analysis_betweenness_centrality", {}, size=(50_000, 200_000))
        decision = guards.guard_expensive_computation(c)
        assert decision.action == "deny"
        assert "50000" in decision.reason
        assert "k=500" in decision.reason

    def test_mitigation_argument_lifts_the_block(self):
        c = ctx("analysis_betweenness_centrality", {"k": 500}, size=(50_000, 200_000))
        assert guards.guard_expensive_computation(c) is None

    def test_allows_small_graphs(self):
        c = ctx("analysis_betweenness_centrality", {}, size=(34, 78))
        assert guards.guard_expensive_computation(c) is None

    def test_denies_kamada_kawai_and_names_an_alternative(self):
        c = ctx("layout_kamada_kawai", {}, size=(20_000, 50_000))
        decision = guards.guard_expensive_computation(c)
        assert decision.action == "deny"
        assert "forceatlas2" in decision.reason

    def test_closeness_has_no_mitigation_so_k_does_not_help(self):
        c = ctx("analysis_closeness_centrality", {"k": 100}, size=(50_000, 200_000))
        assert guards.guard_expensive_computation(c).action == "deny"

    def test_cheap_tools_are_never_blocked(self):
        c = ctx("analysis_degree_centrality", {}, size=(1_000_000, 5_000_000))
        assert guards.guard_expensive_computation(c) is None

    def test_threshold_is_configurable(self, monkeypatch):
        monkeypatch.setenv("AGENT_EXPENSIVE_NODE_THRESHOLD", "100000")
        c = ctx("analysis_betweenness_centrality", {}, size=(50_000, 200_000))
        assert guards.guard_expensive_computation(c) is None

    def test_guard_can_be_disabled(self, monkeypatch):
        monkeypatch.setenv("AGENT_EXPENSIVE_GUARD_ENABLED", "0")
        c = ctx("analysis_betweenness_centrality", {}, size=(50_000, 200_000))
        assert guards.guard_expensive_computation(c) is None


# --------------------------------------------------------------------------
# guard_repeat_call
# --------------------------------------------------------------------------


class TestGuardRepeatCall:
    def test_third_identical_call_is_denied(self):
        state = new_turn_state(10)
        for _ in range(guards.MAX_IDENTICAL_CALLS - 1):
            assert (
                guards.guard_repeat_call(
                    ctx("layout_spring", {"k": 1.0}, turn_state=state)
                )
                is None
            )
        decision = guards.guard_repeat_call(
            ctx("layout_spring", {"k": 1.0}, turn_state=state)
        )
        assert decision.action == "deny"
        assert "already been called" in decision.reason

    def test_different_arguments_are_a_different_call(self):
        state = new_turn_state(10)
        for k in (1.0, 2.0, 3.0, 4.0):
            assert (
                guards.guard_repeat_call(
                    ctx("layout_spring", {"k": k}, turn_state=state)
                )
                is None
            )

    def test_argument_order_does_not_matter(self):
        state = new_turn_state(10)
        guards.guard_repeat_call(ctx("t", {"a": 1, "b": 2}, turn_state=state))
        guards.guard_repeat_call(ctx("t", {"b": 2, "a": 1}, turn_state=state))
        decision = guards.guard_repeat_call(
            ctx("t", {"a": 1, "b": 2}, turn_state=state)
        )
        assert decision.action == "deny"

    def test_different_tools_are_counted_separately(self):
        state = new_turn_state(10)
        for name in ("a", "b", "c", "d"):
            assert guards.guard_repeat_call(ctx(name, {}, turn_state=state)) is None


# --------------------------------------------------------------------------
# guard_consecutive_failures
# --------------------------------------------------------------------------


class TestGuardConsecutiveFailures:
    def test_aborts_after_the_limit(self):
        state = new_turn_state(10)
        for _ in range(guards.MAX_TOOL_FAILURES):
            guards.guard_consecutive_failures(
                ctx("layout_spring", {}, turn_state=state,
                    event=HookEvent.TOOL_ERROR, error="boom")
            )
        assert state["should_abort"] is True
        assert "layout_spring" in state["abort_reason"]

    def test_does_not_abort_below_the_limit(self):
        state = new_turn_state(10)
        for _ in range(guards.MAX_TOOL_FAILURES - 1):
            guards.guard_consecutive_failures(
                ctx("layout_spring", {}, turn_state=state,
                    event=HookEvent.TOOL_ERROR, error="boom")
            )
        assert state["should_abort"] is False

    def test_failures_of_different_tools_do_not_accumulate(self):
        state = new_turn_state(10)
        for name in ("a", "b", "c", "d"):
            guards.guard_consecutive_failures(
                ctx(name, {}, turn_state=state,
                    event=HookEvent.TOOL_ERROR, error="boom")
            )
        assert state["should_abort"] is False

    def test_a_success_clears_the_streak(self):
        """Three failures across a turn that recovered should not abort it."""
        from app.services.llm.hooks.builtin import audit

        state = new_turn_state(10)
        for _ in range(guards.MAX_TOOL_FAILURES - 1):
            guards.guard_consecutive_failures(
                ctx("layout_spring", {}, turn_state=state,
                    event=HookEvent.TOOL_ERROR, error="boom")
            )
        audit.audit_tool_success(
            ctx("layout_spring", {}, turn_state=state, event=HookEvent.POST_TOOL)
        )
        guards.guard_consecutive_failures(
            ctx("layout_spring", {}, turn_state=state,
                event=HookEvent.TOOL_ERROR, error="boom")
        )
        assert state["should_abort"] is False


# --------------------------------------------------------------------------
# stalled-intent detection
# --------------------------------------------------------------------------


class TestDetectStalledIntent:
    @pytest.mark.parametrize(
        "text",
        [
            "I will now calculate the degree centrality.",
            "Let me apply a ForceAtlas2 layout.",
            "I'll color the nodes by community.",
            "次にコミュニティを検出します。",
            "まず、レイアウトを計算します。",
            "PageRank を計算していきます",
            "色分けを適用してみます",
        ],
    )
    def test_detects_announced_actions_in_both_languages(self, text):
        """English-only detection was the original bug; Japanese must fire too."""
        assert intent.detect_stalled_intent(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Shall I size nodes by degree and color by community?",
            "Which would you prefer: community detection or centrality?",
            "コミュニティで色分けしますか？",
            "どちらの方法がよろしいでしょうか。",
            "色分けの方法を教えてください。",
            "Would you like me to calculate centrality?",
            "Let me know which layout you prefer.",
        ],
    )
    def test_does_not_fire_on_questions_to_the_user(self, text):
        """conversation-flow mandates propose-and-wait; that is a complete turn."""
        assert intent.detect_stalled_intent(text) is False

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "The network has 34 nodes and 78 edges.",
            "I will explain what betweenness centrality means.",
            "このネットワークは34ノードです。",
        ],
    )
    def test_does_not_fire_without_an_announced_action(self, text):
        assert intent.detect_stalled_intent(text) is False


class TestIntentHooks:
    def test_nudge_requests_continuation(self):
        c = ctx("x", event=HookEvent.NO_TOOL_CALLS,
                assistant_text="次にコミュニティを検出します。")
        intent.nudge_stalled_intent(c)
        assert c.turn_state["continuation"]["prompt"].startswith(
            "You described an action"
        )

    def test_nudge_respects_the_continuation_budget(self):
        state = new_turn_state(10)
        state["continuations_granted"] = intent.MAX_CONTINUATIONS
        c = ctx("x", turn_state=state, event=HookEvent.NO_TOOL_CALLS,
                assistant_text="次に計算します。")
        intent.nudge_stalled_intent(c)
        assert c.turn_state["continuation"] is None

    def test_forced_summary_fires_when_tools_ran_but_nothing_was_said(self):
        state = new_turn_state(10)
        state["tools_run"] = 2
        c = ctx("x", turn_state=state, event=HookEvent.NO_TOOL_CALLS,
                assistant_text="", thought_text="did the work")
        intent.force_final_summary(c)
        assert "final report" in c.turn_state["continuation"]["prompt"]
        assert "did the work" in c.turn_state["continuation"]["model_text"]

    def test_forced_summary_does_not_fire_when_text_exists(self):
        state = new_turn_state(10)
        state["tools_run"] = 2
        c = ctx("x", turn_state=state, event=HookEvent.NO_TOOL_CALLS,
                assistant_text="Done: layout updated.")
        intent.force_final_summary(c)
        assert c.turn_state["continuation"] is None

    def test_forced_summary_does_not_fire_when_no_tools_ran(self):
        c = ctx("x", event=HookEvent.NO_TOOL_CALLS, assistant_text="")
        intent.force_final_summary(c)
        assert c.turn_state["continuation"] is None


class TestCandidateListing:
    """The deny message is the model's only view of what it can use, so the
    list has to surface real attributes rather than internal storage."""

    def test_layout_coordinate_pairs_are_hidden(self):
        c = ctx(
            "visualization_set_node_color",
            {"attribute": "zzz"},
            node_attrs=[
                "club", "degree_centrality",
                "spring_x", "spring_y", "forceatlas2_x", "forceatlas2_y",
            ],
        )
        reason = guards.guard_attribute_exists(c).reason
        assert "club" in reason and "degree_centrality" in reason
        assert "spring_x" not in reason
        assert "forceatlas2_y" not in reason

    def test_an_unpaired_name_is_kept(self):
        """A user attribute called `pos_x` with no `pos_y` is real data."""
        assert guards._without_layout_coordinates(["pos_x", "club"]) == [
            "pos_x", "club",
        ]

    def test_a_paired_user_attribute_is_the_accepted_cost(self):
        """Genuine x/y pairs are indistinguishable from layout output; hiding
        them is the deliberate tradeoff."""
        assert guards._without_layout_coordinates(
            ["pos_x", "pos_y", "club"]
        ) == ["club"]

    def test_all_hidden_reports_none(self):
        assert guards._format_candidates(["spring_x", "spring_y"]) == "(none)"
