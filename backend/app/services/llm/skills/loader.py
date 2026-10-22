"""Skill file discovery and parsing.

A skill is a Markdown file in `definitions/` with a small YAML-ish frontmatter
block:

    ---
    name: visual-encoding
    description: How to choose colour/size/label mappings and report them.
    triggers: [color, colour, 色分け, サイズ]
    related_tools: [visualization_set_node_color, visualization_set_node_size]
    ---

    ## Procedure
    ...

The frontmatter grammar is deliberately tiny — scalars and string lists, in flow
(`[a, b]`) or block (`- a`) form — so this needs no YAML dependency. Anything
richer belongs in the body, not the header.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"

_FRONTMATTER_FENCE = "---"


class SkillParseError(ValueError):
    """A skill file's frontmatter is malformed or missing required keys."""


@dataclass
class Skill:
    name: str
    description: str
    body: str
    triggers: List[str] = field(default_factory=list)
    related_tools: List[str] = field(default_factory=list)
    source_path: Optional[Path] = None

    def index_line(self) -> str:
        return f"- `{self.name}` — {self.description}"


def _split_frontmatter(text: str) -> Tuple[str, str]:
    """Return (frontmatter, body). Raises if the fenced block is absent."""
    lines = text.lstrip().splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        raise SkillParseError("file does not start with a '---' frontmatter fence")

    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_FENCE:
            return ("\n".join(lines[1:i]), "\n".join(lines[i + 1 :]).strip())

    raise SkillParseError("frontmatter fence is never closed")


def _parse_scalar_or_list(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    return raw.strip("'\"")


def _parse_frontmatter(front: str) -> Dict[str, Any]:
    """Parse the scalar/list subset described in the module docstring."""
    data: Dict[str, Any] = {}
    current_list_key: Optional[str] = None

    for raw_line in front.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue

        # Block-list continuation: "  - value"
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key:
            data[current_list_key].append(stripped[2:].strip().strip("'\""))
            continue

        if ":" not in line:
            raise SkillParseError(f"cannot parse frontmatter line: {raw_line!r}")

        key, _, value = line.partition(":")
        key = key.strip()
        parsed = _parse_scalar_or_list(value)

        if parsed == "" or parsed == []:
            # Either an empty scalar or the header of a block list; assume list
            # and let a following "- " line fill it. An empty value stays [].
            data[key] = [] if parsed == [] else []
            current_list_key = key
            continue

        data[key] = parsed
        current_list_key = None

    return data


def parse_skill(text: str, source_path: Optional[Path] = None) -> Skill:
    front, body = _split_frontmatter(text)
    data = _parse_frontmatter(front)

    name = data.get("name")
    description = data.get("description")
    if not name or not isinstance(name, str):
        raise SkillParseError("frontmatter is missing a 'name' string")
    if not description or not isinstance(description, str):
        raise SkillParseError(f"skill '{name}' is missing a 'description' string")
    if not body.strip():
        raise SkillParseError(f"skill '{name}' has an empty body")

    def as_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]

    return Skill(
        name=name,
        description=description,
        body=body,
        triggers=as_list(data.get("triggers")),
        related_tools=as_list(data.get("related_tools")),
        source_path=source_path,
    )


def load_skills(directory: Optional[Path] = None) -> List[Skill]:
    """Parse every `*.md` in `directory`, skipping (and logging) bad files.

    A malformed skill must not take down the agent: the rest of the catalogue
    still loads and the model simply cannot reach the broken one.
    """
    directory = directory or DEFINITIONS_DIR
    if not directory.is_dir():
        logger.warning(f"Skill directory not found: {directory}")
        return []

    skills: List[Skill] = []
    seen: Dict[str, Path] = {}

    for path in sorted(directory.glob("*.md")):
        try:
            skill = parse_skill(path.read_text(encoding="utf-8"), source_path=path)
        except (SkillParseError, OSError) as e:
            logger.error(f"Skipping skill file {path.name}: {e}")
            continue

        if skill.name in seen:
            logger.error(
                f"Duplicate skill name '{skill.name}' in {path.name}; "
                f"already defined by {seen[skill.name].name}. Skipping."
            )
            continue

        seen[skill.name] = path
        skills.append(skill)

    logger.info(f"Loaded {len(skills)} skills from {directory}")
    return skills
