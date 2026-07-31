"""Skill catalogue with progressive disclosure.

The system prompt carries only `index_block()` — one line per skill. Full
procedures are fetched on demand through the `skill_load` tool. That is the
whole point of the mechanism: before this, every request paid for the full text
of every playbook in `prompts.py`, whether the user asked to recolour a graph or
just asked how many nodes it has.

`suggest()` is a nudge, not a gate. It keyword-matches the user's message and
names likely-relevant skills in the prompt, but the model can load any skill
from the index regardless of whether the keywords fired — which matters because
keyword matching across Japanese and English is exactly the kind of brittle
heuristic this codebase already got burned by (see hooks/builtin/intent.py).
"""

import threading
from pathlib import Path
from typing import Dict, List, Optional

from app.core.logging import get_logger

from .loader import Skill, load_skills

logger = get_logger(__name__)


class SkillRegistry:
    def __init__(self, directory: Optional[Path] = None) -> None:
        self._directory = directory
        self._skills: Dict[str, Skill] = {}
        self._lock = threading.Lock()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._skills = {s.name: s for s in load_skills(self._directory)}
            self._loaded = True

    def reload(self) -> None:
        with self._lock:
            self._skills = {s.name: s for s in load_skills(self._directory)}
            self._loaded = True

    # --- access ---

    def all(self) -> List[Skill]:
        self._ensure_loaded()
        return list(self._skills.values())

    def names(self) -> List[str]:
        self._ensure_loaded()
        return list(self._skills.keys())

    def get(self, name: str) -> Optional[Skill]:
        """Look up a skill, tolerating case and separator differences.

        Models reliably produce `visual_encoding` for a skill named
        `visual-encoding`, and refusing that would waste an iteration on a
        typo-level mismatch.
        """
        self._ensure_loaded()
        if name in self._skills:
            return self._skills[name]

        normalized = self._normalize(name)
        for candidate, skill in self._skills.items():
            if self._normalize(candidate) == normalized:
                return skill
        return None

    @staticmethod
    def _normalize(name: str) -> str:
        return name.strip().lower().replace("_", "-").replace(" ", "-")

    # --- prompt surfaces ---

    def index_block(self) -> str:
        """The always-on skill index for the system prompt."""
        self._ensure_loaded()
        if not self._skills:
            return ""

        lines = [s.index_line() for s in self._skills.values()]
        return (
            "# Skills\n"
            "Detailed procedures are stored outside this prompt. Load one with "
            "`skill_load(name)` before acting on the kind of request it covers, "
            "and follow it — the loaded text takes precedence over your general "
            "instincts about how to work with this tool set. Loading is cheap; "
            "guessing at a procedure you have not read is not.\n\n"
            "Available skills:\n" + "\n".join(lines)
        )

    def suggest(self, text: str, limit: int = 3) -> List[Skill]:
        """Skills whose triggers appear in `text`, best match first.

        Matching is substring-based and case-insensitive. Japanese has no word
        boundaries to anchor on, so substring matching is the only option that
        works for both languages; the cost of a spurious suggestion is one line
        of prompt, so a loose match is the right tradeoff.
        """
        self._ensure_loaded()
        if not text:
            return []

        lowered = text.lower()
        scored = []
        for skill in self._skills.values():
            hits = sum(1 for t in skill.triggers if t and t.lower() in lowered)
            if hits:
                scored.append((hits, skill))

        scored.sort(key=lambda pair: (-pair[0], pair[1].name))
        return [skill for _hits, skill in scored[:limit]]

    def suggestion_block(self, text: str, limit: int = 3) -> str:
        matches = self.suggest(text, limit=limit)
        if not matches:
            return ""
        names = ", ".join(f"`{s.name}`" for s in matches)
        return (
            f"Skills likely relevant to this request: {names}. "
            f"Load what you need with `skill_load` before acting."
        )


# Process-wide catalogue; skill files are read once and held in memory.
registry = SkillRegistry()
