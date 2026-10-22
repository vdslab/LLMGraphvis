"""Agent skills: procedural playbooks loaded on demand.

See `registry.py` for the progressive-disclosure design and `definitions/` for
the skills themselves.
"""

from .loader import Skill, SkillParseError, load_skills, parse_skill
from .registry import SkillRegistry, registry

__all__ = [
    "Skill",
    "SkillParseError",
    "SkillRegistry",
    "load_skills",
    "parse_skill",
    "registry",
]
