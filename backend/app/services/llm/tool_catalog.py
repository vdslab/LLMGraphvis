"""Per-turn progressive disclosure for provider tool definitions."""

import os
import re
from dataclasses import dataclass
from typing import Iterable

from .providers.types import ToolDefinition

INITIAL_TOOL_NAMES = ("skill_load", "tool_search", "ask_user")
DEPRECATED_TOOL_NAMES = frozenset(
    {"network_initialize", "visualization_apply_layout", "analysis_detect_communities"}
)


def exposure_mode() -> str:
    value = (os.getenv("TOOL_EXPOSURE_MODE") or "progressive").strip().lower()
    return value if value in {"progressive", "all"} else "progressive"


@dataclass(frozen=True)
class SearchResult:
    tool: ToolDefinition
    score: tuple[int, int, str]


class ToolCatalog:
    """Immutable full catalogue plus operations on per-turn enabled names."""

    def __init__(self, tools: Iterable[ToolDefinition]) -> None:
        self._tools = tuple(tools)
        self._by_name = {tool.name: tool for tool in self._tools}

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def initialize_turn(
        self, turn_state: dict, restore: Iterable[str] | None = None
    ) -> None:
        """Seed this turn's exposure set.

        `restore` carries an earlier turn's exposure across an `ask_user`
        answer, which resumes the same task (ADR 0014). Names that no longer
        exist in the catalogue are dropped, so a renamed tool degrades to
        "load it again" rather than to a call that cannot be executed.
        """
        turn_state["tool_catalog"] = self
        if exposure_mode() == "all":
            enabled = set(self._by_name)
        else:
            enabled = {name for name in INITIAL_TOOL_NAMES if name in self._by_name}
        restored = {name for name in (restore or ()) if name in self._by_name}
        enabled |= restored
        turn_state["enabled_tool_names"] = enabled
        turn_state["restored_tool_names"] = restored
        turn_state["presented_tool_names"] = set()

    def get(self, name: str) -> ToolDefinition | None:
        return self._by_name.get(name)

    def active_names(self, turn_state: dict) -> list[str]:
        """Every name currently exposed, not just the most recent addition."""
        enabled = turn_state.get("enabled_tool_names", set())
        return sorted(name for name in enabled if name in self._by_name)

    def active_tools(self, turn_state: dict) -> list[ToolDefinition]:
        enabled = turn_state.get("enabled_tool_names", set())
        return [tool for tool in self._tools if tool.name in enabled]

    def activate(self, names: Iterable[str], turn_state: dict) -> tuple[list[str], list[str]]:
        enabled = turn_state.setdefault("enabled_tool_names", set())
        activated: list[str] = []
        missing: list[str] = []
        for name in names:
            if name not in self._by_name:
                missing.append(name)
            elif name not in enabled:
                enabled.add(name)
                activated.append(name)
        return activated, missing

    def search(self, query: str) -> list[ToolDefinition]:
        normalized = query.strip().lower().replace("-", "_")
        if not normalized:
            return []
        terms = [term for term in re.split(r"[\s,、]+", normalized) if term]
        skill_text = self._skill_search_text()
        matches: list[SearchResult] = []

        for tool in self._tools:
            name = tool.name.lower()
            exact = normalized == name
            if tool.name in DEPRECATED_TOOL_NAMES and not exact:
                continue
            description = tool.description.lower()
            related = skill_text.get(tool.name, "")
            if exact:
                score = (0, 0, name)
            elif name.startswith(normalized):
                score = (1, 0, name)
            elif all(term in name for term in terms):
                score = (2, len(name), name)
            elif all(term in description for term in terms):
                score = (3, len(description), name)
            elif all(term in related for term in terms):
                score = (4, len(related), name)
            elif len(terms) > 1 and (
                matched := _terms_matched(terms, name, description, related)
            ):
                # A query that names a real tool plus extra words ("node_size
                # scaling factor") matches every field partially and none of them
                # wholly. Returning nothing there sends the model into a retry
                # loop against a tool that exists, so rank partial hits last
                # rather than dropping them. Single-term queries cannot reach
                # this branch, so strict behaviour is unchanged for them.
                score = (5, -matched, name)
            else:
                continue
            matches.append(SearchResult(tool, score))

        matches.sort(key=lambda match: match.score)
        return [match.tool for match in matches]

    @staticmethod
    def _skill_search_text() -> dict[str, str]:
        from .skills import registry

        text: dict[str, list[str]] = {}
        for skill in registry.all():
            searchable = " ".join([skill.name, skill.description, *skill.triggers]).lower()
            for tool_name in skill.related_tools:
                text.setdefault(tool_name, []).append(searchable)
        return {name: " ".join(parts) for name, parts in text.items()}


def tool_definition_bytes(tools: Iterable[ToolDefinition]) -> int:
    """Return serialized definition size for observability; this is not tokens."""
    import json

    return len(
        json.dumps(
            [tool.__dict__ for tool in tools], ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
    )


def _terms_matched(terms: list[str], *fields: str) -> int:
    """How many of `terms` appear in any of `fields`."""
    return sum(any(term in field for field in fields) for term in terms)
