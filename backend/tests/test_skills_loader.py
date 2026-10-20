"""Tests for the skill loader and registry."""

import textwrap
from pathlib import Path

import pytest
from app.services.llm.skills.loader import (
    Skill,
    SkillParseError,
    load_skills,
    parse_skill,
)
from app.services.llm.skills.registry import SkillRegistry


def write_skill(directory: Path, filename: str, content: str) -> Path:
    path = directory / filename
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


VALID = """
    ---
    name: demo-skill
    description: A demo skill for tests.
    triggers: [colour, 色分け]
    related_tools: [visualization_set_node_color]
    ---

    ## Procedure
    Do the thing.
    """


class TestParseSkill:
    def test_parses_flow_lists(self):
        skill = parse_skill(textwrap.dedent(VALID).lstrip())
        assert skill.name == "demo-skill"
        assert skill.description == "A demo skill for tests."
        assert skill.triggers == ["colour", "色分け"]
        assert skill.related_tools == ["visualization_set_node_color"]
        assert "Do the thing." in skill.body

    def test_parses_block_lists(self):
        skill = parse_skill(
            textwrap.dedent(
                """
                ---
                name: block
                description: Block-style lists.
                triggers:
                  - alpha
                  - beta
                ---

                Body.
                """
            ).lstrip()
        )
        assert skill.triggers == ["alpha", "beta"]

    def test_strips_quotes_from_values(self):
        skill = parse_skill(
            textwrap.dedent(
                """
                ---
                name: 'quoted'
                description: "Has quotes."
                triggers: ['a', "b"]
                ---

                Body.
                """
            ).lstrip()
        )
        assert skill.name == "quoted"
        assert skill.description == "Has quotes."
        assert skill.triggers == ["a", "b"]

    def test_missing_frontmatter_fence_raises(self):
        with pytest.raises(SkillParseError, match="frontmatter fence"):
            parse_skill("name: x\n\nBody.")

    def test_unclosed_frontmatter_raises(self):
        with pytest.raises(SkillParseError, match="never closed"):
            parse_skill("---\nname: x\ndescription: y\n\nBody.")

    def test_missing_name_raises(self):
        with pytest.raises(SkillParseError, match="missing a 'name'"):
            parse_skill("---\ndescription: y\n---\n\nBody.")

    def test_missing_description_raises(self):
        with pytest.raises(SkillParseError, match="missing a 'description'"):
            parse_skill("---\nname: x\n---\n\nBody.")

    def test_empty_body_raises(self):
        with pytest.raises(SkillParseError, match="empty body"):
            parse_skill("---\nname: x\ndescription: y\n---\n\n   \n")

    def test_optional_lists_default_to_empty(self):
        skill = parse_skill("---\nname: x\ndescription: y\n---\n\nBody.")
        assert skill.triggers == []
        assert skill.related_tools == []


class TestLoadSkills:
    def test_loads_every_valid_file(self, tmp_path):
        write_skill(tmp_path, "a.md", VALID)
        write_skill(tmp_path, "b.md", VALID.replace("demo-skill", "other-skill"))
        skills = load_skills(tmp_path)
        assert sorted(s.name for s in skills) == ["demo-skill", "other-skill"]

    def test_a_malformed_file_does_not_break_the_rest(self, tmp_path):
        """One bad skill must not make the agent lose its whole catalogue."""
        write_skill(tmp_path, "good.md", VALID)
        write_skill(tmp_path, "bad.md", "no frontmatter here")
        skills = load_skills(tmp_path)
        assert [s.name for s in skills] == ["demo-skill"]

    def test_duplicate_names_keep_only_the_first(self, tmp_path):
        write_skill(tmp_path, "a.md", VALID)
        write_skill(tmp_path, "z.md", VALID)
        skills = load_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].source_path.name == "a.md"

    def test_missing_directory_returns_empty(self, tmp_path):
        assert load_skills(tmp_path / "nope") == []

    def test_ignores_non_markdown(self, tmp_path):
        write_skill(tmp_path, "a.md", VALID)
        (tmp_path / "notes.txt").write_text("---\nname: t\ndescription: d\n---\n\nx")
        assert len(load_skills(tmp_path)) == 1


class TestSkillRegistry:
    @pytest.fixture
    def registry(self, tmp_path):
        write_skill(
            tmp_path,
            "colour.md",
            """
            ---
            name: visual-encoding
            description: Colour and size mappings.
            triggers: [colour, color, 色分け, サイズ]
            ---

            Colour body.
            """,
        )
        write_skill(
            tmp_path,
            "layout.md",
            """
            ---
            name: layout-tuning
            description: Layout parameters.
            triggers: [layout, レイアウト, 広げ]
            ---

            Layout body.
            """,
        )
        return SkillRegistry(tmp_path)

    def test_names_and_get(self, registry):
        assert sorted(registry.names()) == ["layout-tuning", "visual-encoding"]
        assert registry.get("layout-tuning").body == "Layout body."

    def test_get_tolerates_underscores_and_case(self, registry):
        """Models reliably produce layout_tuning for a skill named layout-tuning."""
        assert registry.get("layout_tuning").name == "layout-tuning"
        assert registry.get("Layout-Tuning").name == "layout-tuning"
        assert registry.get(" layout-tuning ").name == "layout-tuning"

    def test_get_unknown_returns_none(self, registry):
        assert registry.get("nope") is None

    def test_index_block_lists_every_skill_with_its_description(self, registry):
        block = registry.index_block()
        assert "skill_load" in block
        assert "`visual-encoding` — Colour and size mappings." in block
        assert "`layout-tuning` — Layout parameters." in block

    def test_index_block_empty_when_no_skills(self, tmp_path):
        assert SkillRegistry(tmp_path / "nope").index_block() == ""

    def test_suggest_matches_english(self, registry):
        assert [s.name for s in registry.suggest("change the color please")] == [
            "visual-encoding"
        ]

    def test_suggest_matches_japanese(self, registry):
        """The trigger lists must work for the app's primary UX language."""
        assert [s.name for s in registry.suggest("ノードを広げてほしい")] == [
            "layout-tuning"
        ]
        assert [s.name for s in registry.suggest("色分けして")] == ["visual-encoding"]

    def test_suggest_ranks_by_hit_count(self, registry):
        # Two visual-encoding triggers match (color, サイズ) against one for
        # layout-tuning, so visual-encoding must rank first.
        matches = registry.suggest("color とサイズを変えて、layout も調整して")
        assert [s.name for s in matches] == ["visual-encoding", "layout-tuning"]

    def test_suggest_breaks_ties_by_name(self, registry):
        matches = registry.suggest("change the color and the layout")
        assert sorted(s.name for s in matches) == ["layout-tuning", "visual-encoding"]

    def test_suggest_respects_limit(self, registry):
        assert len(registry.suggest("color layout", limit=1)) == 1

    def test_suggest_returns_empty_on_no_match(self, registry):
        assert registry.suggest("how many nodes are there") == []
        assert registry.suggest("") == []

    def test_suggestion_block_empty_on_no_match(self, registry):
        assert registry.suggestion_block("how many nodes") == ""
        assert "`visual-encoding`" in registry.suggestion_block("color")

    def test_reload_picks_up_new_files(self, registry, tmp_path):
        assert len(registry.names()) == 2
        write_skill(
            tmp_path,
            "new.md",
            "---\nname: added\ndescription: Added later.\n---\n\nBody.",
        )
        registry.reload()
        assert "added" in registry.names()


class TestShippedSkills:
    """The real definitions/ directory must stay loadable and well-formed."""

    def test_all_shipped_skills_parse(self):
        skills = load_skills()
        assert len(skills) >= 6, "shipped skill definitions failed to load"

    def test_shipped_skills_have_triggers_in_both_languages(self):
        """A skill with only English triggers is invisible to Japanese requests."""
        for skill in load_skills():
            assert skill.triggers, f"{skill.name} has no triggers"
            has_japanese = any(
                any(ord(ch) > 0x3000 for ch in trigger) for trigger in skill.triggers
            )
            assert has_japanese, f"{skill.name} has no Japanese triggers"

    def test_visual_encoding_activates_both_node_channels(self):
        """A composite encoding must be reachable in one skill_load.

        Colour and size are set by separate tools; if loading the skill activates
        only one of them, the model can only build half the view it just read
        about, and the second channel costs another round trip it usually skips.
        """
        skill = next(s for s in load_skills() if s.name == "visual-encoding")
        assert "visualization_set_node_color" in skill.related_tools
        assert "visualization_set_node_size" in skill.related_tools

    @pytest.mark.parametrize(
        "request_text, expected, not_first",
        [
            ("このノードに注目したい", "view-navigation", "subgraph-workflow"),
            ("AからBへの経路を表示して", "view-navigation", None),
            ("もう少しズームして", "view-navigation", "subgraph-workflow"),
            ("全体が見えるように戻して", "view-navigation", None),
            ("引きで見せて", "view-navigation", None),
            ("zoom out and show everything", "view-navigation", None),
            ("ラベルの文字サイズを大きくして", "labels", "visual-encoding"),
            ("このコミュニティだけ抽出して", "subgraph-workflow", None),
        ],
    )
    def test_view_requests_reach_view_skills(self, request_text, expected, not_first):
        """Looking at part of the network must not be routed to extraction."""
        registry = SkillRegistry()
        names = [s.name for s in registry.suggest(request_text)]
        assert expected in names, names
        if not_first:
            assert names[0] != not_first, names

    @pytest.mark.parametrize(
        "request_text, expected",
        [
            ("このデータで何がわかる？", "analysis-planning"),
            ("全体像が知りたい", "analysis-planning"),
            ("どこから見ればいい？", "analysis-planning"),
            ("誰が一番影響力ある？", "analysis-planning"),
            ("人気者は誰？", "analysis-planning"),
            ("まとめ役は誰？", "analysis-planning"),
            ("who is the most popular person?", "analysis-planning"),
            ("橋渡しをしている人を知りたい", "network-metrics"),
            ("孤立している人はいる？", "network-metrics"),
            ("who acts as a broker?", "network-metrics"),
            ("AさんとBさんはどうつながってる？", "path-analysis"),
            ("初めてなので何をすればいいかわからない", "conversation-flow"),
            ("外れ値で色の違いがわからない", "visual-encoding"),
            ("make the edges more transparent", "visual-encoding"),
        ],
    )
    def test_plain_language_requests_reach_a_skill(self, request_text, expected):
        """Beginners describe the question, not the method.

        Only skill_load, tool_search and ask_user are callable at turn start, so
        a request no trigger matches leaves a small model to guess the skill.
        """
        names = [s.name for s in SkillRegistry().suggest(request_text)]
        assert expected in names, names

    @pytest.mark.parametrize(
        "request_text, expected",
        [
            ("エッジを細く薄くして", "visual-encoding"),
            ("他のノードを薄くして", "view-navigation"),
        ],
    )
    def test_faint_means_style_for_edges_and_focus_for_others(
        self, request_text, expected
    ):
        """'薄く' is a focus when it dims the rest, a style when it names edges."""
        names = [s.name for s in SkillRegistry().suggest(request_text)]
        assert names and names[0] == expected, names

    def test_index_block_is_much_smaller_than_the_bodies(self):
        """Progressive disclosure only pays off if the index stays small."""
        skills = load_skills()
        index = "\n".join(s.index_line() for s in skills)
        bodies = sum(len(s.body) for s in skills)
        assert len(index) < bodies / 4

    def test_cross_references_between_skills_resolve(self):
        """A skill telling the model to "see `x-skill`" must name a real skill.

        The bodies cross-reference each other by name; a stale reference sends the
        model to `skill_load` with a name that does not exist.
        """
        import re

        skills = load_skills()
        names = {s.name for s in skills}
        # Only check backticked identifiers that look like skill names
        # (kebab-case, no underscores), so tool names are not swept in.
        candidate = re.compile(r"`([a-z]+(?:-[a-z]+)+)`")
        for skill in skills:
            for ref in set(candidate.findall(skill.body)):
                suffixes = (
                    "-tuning", "-flow", "-planning",
                    "-encoding", "-workflow", "-recovery",
                    "-navigation", "-analysis",
                )
                if ref.endswith(suffixes) or ref.startswith("layout-"):
                    assert ref in names, (
                        f"{skill.name} references unknown skill '{ref}'"
                    )


# The arguments each layout tool accepts, as declared in
# networkx-api/app/mcp/tools/layout/. The backend cannot import that service,
# so this copy is what a layout skill is checked against: a skill naming a
# parameter its tool does not have sends the model into a validation error.
LAYOUT_TOOL_ARGUMENTS = {
    "forceatlas2": {
        "max_iter", "gravity", "scaling_ratio", "jitter_tolerance", "strong_gravity",
        "linlog", "distributed_action", "node_mass", "size_aware", "node_size",
        "weight", "seed", "pos", "init_from_layout", "force_recompute",
    },
    "spring": {
        "iterations", "k", "threshold", "method", "gravity", "fixed", "weight",
        "scale", "center", "seed", "pos", "init_from_layout", "force_recompute",
    },
    "arf": {
        "scaling", "a", "etol", "dt", "max_iter", "seed", "pos",
        "init_from_layout", "force_recompute",
    },
    "kamada_kawai": {
        "weight", "dist", "scale", "center", "pos", "init_from_layout",
        "force_recompute",
    },
    "bipartite": {
        "partition_attribute", "partition_value", "nodes", "align", "aspect_ratio",
        "scale", "center", "force_recompute",
    },
    "multipartite": {
        "subset_attribute", "subset_key", "align", "scale", "center", "force_recompute",
    },
    "shell": {"nlist", "rotate", "scale", "center", "force_recompute"},
    "bfs": {"start", "align", "scale", "center", "force_recompute"},
}

# Backticked words in a layout skill that are not parameters.
_NOT_PARAMETERS = {
    "layout", "layout_quality", "score", "issues", "knobs", "arguments", "tradeoff",
    "metric_deltas", "stopped_early", "recommended", "unsuitable", "none",
    "node_overlap", "outliers_compress_core", "clumped", "uneven_edge_lengths",
    "distorted_aspect", "louvain_community",
}


class TestLayoutSkills:
    """The two-layer layout skills (ADR 0017)."""

    def _layout_skills(self):
        return [s for s in load_skills() if s.name.startswith("layout-")]

    def test_every_algorithm_skill_exposes_its_tools(self):
        for skill in self._layout_skills():
            layout_tools = [t for t in skill.related_tools if t.startswith("layout_")]
            assert any(t[len("layout_"):] in LAYOUT_TOOL_ARGUMENTS for t in layout_tools), skill.name
            assert "visualization_generate" in skill.related_tools, skill.name

    def test_algorithm_skills_name_only_real_parameters(self):
        import re

        token = re.compile(r"`([a-z][a-z0-9_]*)(?:=[^`]*)?`")
        for skill in self._layout_skills():
            layouts = [
                t[len("layout_"):]
                for t in skill.related_tools
                if t[len("layout_"):] in LAYOUT_TOOL_ARGUMENTS
            ]
            allowed = set().union(*(LAYOUT_TOOL_ARGUMENTS[name] for name in layouts))
            for word in set(token.findall(skill.body)):
                if word.startswith(("layout_", "visualization_")) or word in _NOT_PARAMETERS:
                    continue
                assert word in allowed, f"{skill.name} names unknown parameter `{word}`"

    def test_layout_skills_state_no_numbers(self):
        """Defaults and ranges live in code; a number in a skill goes stale."""
        import re

        for skill in load_skills():
            if skill.name == "layout" or skill.name.startswith("layout-"):
                # Neither a digit inside a name (ForceAtlas2) nor a list marker
                # is a stated value.
                body = re.sub(r"(?m)^\d+\. ", "", skill.body)
                number = re.search(r"(?<![A-Za-z_])\d", body)
                assert not number, f"{skill.name} states a number"

    def test_current_layout_skill_joins_the_suggestion(self):
        from app.services.llm.skills.registry import SkillRegistry

        registry = SkillRegistry()
        block = registry.suggestion_block("もう少し広げて", current_layout="forceatlas2")
        assert "`layout`" in block and "`layout-forceatlas2`" in block
        partitioned = registry.suggestion_block("レイアウトを整えて", current_layout="bfs")
        assert "`layout-partitioned`" in partitioned

    @pytest.mark.parametrize("answer", ["おまかせで調整", "今の値から自分で調整", "このままでよい"])
    def test_each_answer_to_the_tuning_question_reaches_the_layout_skill(self, answer):
        """The answer arrives in the next turn (ADR 0018); its procedure is in `layout`."""
        from app.services.llm.skills.registry import SkillRegistry

        names = [s.name for s in SkillRegistry().suggest(answer)]
        assert "layout" in names

    def test_no_algorithm_skill_without_a_layout_request(self):
        from app.services.llm.skills.registry import SkillRegistry

        block = SkillRegistry().suggestion_block("色分けして", current_layout="forceatlas2")
        assert "layout-forceatlas2" not in block

    def test_layout_without_a_skill_adds_nothing(self):
        from app.services.llm.skills.registry import SkillRegistry

        block = SkillRegistry().suggestion_block("レイアウト", current_layout="circular")
        assert "`layout`" in block and "layout-" not in block


def test_skill_dataclass_index_line():
    skill = Skill(name="a", description="B.", body="x")
    assert skill.index_line() == "- `a` — B."
