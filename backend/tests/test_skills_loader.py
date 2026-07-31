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
                )
                if ref.endswith(suffixes):
                    assert ref in names, (
                        f"{skill.name} references unknown skill '{ref}'"
                    )


def test_skill_dataclass_index_line():
    skill = Skill(name="a", description="B.", body="x")
    assert skill.index_line() == "- `a` — B."
