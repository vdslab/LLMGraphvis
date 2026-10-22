"""Agent lifecycle hooks.

See `types.py` for the event list and `registry.py` for dispatch. Builtin hooks
live in `builtin/` and register themselves when `load_builtin_hooks()` runs.
"""

from .registry import HookRegistry, build_context, hook, load_builtin_hooks, registry
from .types import (
    HookContext,
    HookEvent,
    ToolCallDecision,
    new_turn_state,
)

__all__ = [
    "HookContext",
    "HookEvent",
    "HookRegistry",
    "ToolCallDecision",
    "build_context",
    "hook",
    "load_builtin_hooks",
    "new_turn_state",
    "registry",
]
