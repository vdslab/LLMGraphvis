"""Keep AGENTS.md honest.

AGENTS.md is loaded into every coding agent's context, so a stale claim in it is
worse than no claim at all — `knowledge.md`, which this file replaces the need
for, drifted for months while instructing agents to trust it.

The documentation policy in `specification/README.md` says derivable facts belong
in code, not prose, so AGENTS.md deliberately carries no tool counts. What it
does carry is *names* — of hook events, local tools, deprecated tools, and files.
Those are what this module checks.
"""

import re
import subprocess
from pathlib import Path

import pytest
from app.services.llm.hooks.types import HookEvent
from app.services.llm.local_tools import LOCAL_TOOL_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# Antigravity truncates a rules file past 12,000 characters without warning, and
# it reads AGENTS.md as a rules file. Leave headroom so an edit does not silently
# drop the tail of the document for one of the tools that reads it.
ANTIGRAVITY_RULE_LIMIT = 12_000
BUDGET = 11_000

# Paths AGENTS.md names precisely because they must NOT exist. Creating either
# would silently break something: llm_service.py is the stale instruction agents
# keep being told to edit, and .gemini/.env shadows the root .env for Gemini CLI.
MUST_NOT_EXIST = {
    "backend/app/services/llm_service.py",
    ".gemini/.env",
}


@pytest.fixture(scope="module")
def agents_md() -> str:
    return AGENTS_MD.read_text(encoding="utf-8")


def test_agents_md_fits_in_the_rules_file_limit(agents_md: str) -> None:
    size = len(agents_md)
    assert size <= BUDGET, (
        f"AGENTS.md is {size} characters, over the {BUDGET} budget "
        f"(hard limit {ANTIGRAVITY_RULE_LIMIT}). Move rationale into "
        f"specification/ rather than raising this number."
    )


def test_hook_events_named_in_agents_md_exist(agents_md: str) -> None:
    for event in HookEvent:
        name = event.name
        assert name in agents_md, f"AGENTS.md does not mention hook event {name}"


def test_every_hook_event_in_agents_md_is_real(agents_md: str) -> None:
    """A renamed or removed event must not linger in the docs."""
    documented = {
        line.split("`")[1]
        for line in agents_md.splitlines()
        if line.startswith("| `") and line.split("`")[1].isupper()
    }
    real = {event.name for event in HookEvent}
    assert documented <= real, (
        f"AGENTS.md names hook events that do not exist: {documented - real}"
    )


def test_local_tools_named_in_agents_md_exist(agents_md: str) -> None:
    for name in LOCAL_TOOL_NAMES:
        assert name in agents_md, f"AGENTS.md does not mention local tool {name}"


def _candidate_paths(text: str) -> set[str]:
    """Backticked tokens in AGENTS.md that look like a repo path.

    AGENTS.md refers to files by whatever prefix is unambiguous in context
    (`llm/emitters.py`, `logic/layouts/base.py`), so these are matched as
    suffixes rather than repo-relative paths.
    """
    out: set[str] = set()
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.strip().rstrip(".,;:)")
        if "/" not in token:
            continue
        # Not paths: URIs, globs, templates, prose, absolute paths, ranges.
        if any(c in token for c in "{}*<> ") or "://" in token or token.startswith("/"):
            continue
        if "..." in token:  # elided path, e.g. backend/.../local_tools.py
            continue
        if token in MUST_NOT_EXIST:
            continue
        if not re.fullmatch(r"[\w.\-/]+", token):
            continue
        out.add(token.rstrip("/"))
    return out


@pytest.fixture(scope="module")
def tracked_paths() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


def test_every_path_agents_md_names_exists(
    agents_md: str, tracked_paths: list[str]
) -> None:
    """A path that no longer exists is exactly how a guide starts lying."""
    missing = []
    for candidate in sorted(_candidate_paths(agents_md)):
        if (REPO_ROOT / candidate).exists():
            continue
        if any(p == candidate or p.endswith("/" + candidate) for p in tracked_paths):
            continue
        # Directory referred to by a suffix, e.g. "llm/hooks/builtin".
        if any(f"/{candidate}/" in f"/{p}" for p in tracked_paths):
            continue
        missing.append(candidate)
    assert not missing, f"AGENTS.md references paths that do not exist: {missing}"


@pytest.mark.parametrize("path", sorted(MUST_NOT_EXIST))
def test_paths_agents_md_says_are_absent_really_are(agents_md: str, path: str) -> None:
    """AGENTS.md tells agents these do not exist. Keep that true."""
    assert path in agents_md, (
        f"AGENTS.md no longer mentions {path}; drop it from MUST_NOT_EXIST"
    )
    assert not (REPO_ROOT / path).exists(), (
        f"{path} exists, but AGENTS.md says it must not"
    )


def test_pointer_files_do_not_duplicate_agents_md() -> None:
    """CLAUDE.md and the Antigravity rules must stay pointers, not copies."""
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in claude_md
    assert len(claude_md) < 500, "CLAUDE.md should point at AGENTS.md, not restate it"

    rule = (REPO_ROOT / ".agent/rules/specification.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in rule
