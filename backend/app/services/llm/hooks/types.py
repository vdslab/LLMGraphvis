"""Types for the agent hook system.

Hooks are the extension point around the ReAct loop in `engine.py`. They replace
behaviour that used to be hardcoded there as if/elif chains over tool names
(auto-rendering, network switching, `network_id` injection), and they add
enforcement that previously existed only as prose in the system prompt
(attribute verification, cost limits, loop termination).

The key property a hook has that a prompt instruction does not: a PRE_TOOL hook
can *deny* a call. The model cannot talk its way past it.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


class HookEvent(str, Enum):
    """Points in a turn where hooks run."""

    # Once per turn, before the first generate(). Hooks may contribute extra
    # system-prompt context via HookContext.context_additions.
    TURN_START = "turn_start"

    # Before every tool call. Hooks may allow / modify args / deny the call.
    PRE_TOOL = "pre_tool"

    # After a tool call that completed successfully. Side effects live here
    # (rendering, chat state updates).
    POST_TOOL = "post_tool"

    # After a tool call that raised, or that a PRE_TOOL hook denied.
    TOOL_ERROR = "tool_error"

    # An iteration produced no tool calls, so the turn is about to end. Hooks may
    # request one more round via HookContext.request_continuation() — this is
    # where the "announced an action but did not take it" nudge and the forced
    # final summary live.
    NO_TOOL_CALLS = "no_tool_calls"

    # Once per turn, after the loop finishes (normally or by abort).
    TURN_END = "turn_end"


ToolCallAction = Literal["allow", "deny", "modify"]


@dataclass
class ToolCallDecision:
    """A PRE_TOOL hook's verdict on a pending tool call.

    A hook returning `None` is equivalent to `allow()`.

    On `deny`, the engine does not invoke the tool. It records
    `{"error": reason, "blocked_by": hook_name}` as the tool result and appends
    it to history like any other result, so the model reads the reason and can
    self-correct on the next iteration.
    """

    action: ToolCallAction = "allow"
    # For "modify": the full replacement args dict.
    args: Optional[Dict[str, Any]] = None
    # For "deny": shown to the model. For "modify": optional note appended to
    # the tool result so the model knows its arguments were adjusted.
    reason: Optional[str] = None
    # Filled in by the registry so the model (and the audit log) can see which
    # hook was responsible.
    hook_name: Optional[str] = None

    @classmethod
    def allow(cls) -> "ToolCallDecision":
        return cls(action="allow")

    @classmethod
    def deny(cls, reason: str) -> "ToolCallDecision":
        return cls(action="deny", reason=reason)

    @classmethod
    def modify(
        cls, args: Dict[str, Any], reason: Optional[str] = None
    ) -> "ToolCallDecision":
        return cls(action="modify", args=args, reason=reason)


@dataclass
class HookContext:
    """Everything a hook can read or influence.

    One instance is built per hook invocation, but `turn_state` is shared by
    reference across every hook in a turn — that is how cross-call state
    (repeat-call counters, failure counters, the abort flag) is accumulated.
    """

    event: HookEvent
    chat_id: int
    network_id: int
    # Shared per-turn scratch space. See TurnState for the keys in use.
    turn_state: Dict[str, Any]

    db: Any = None
    queue: Any = None
    # Live MCP ClientSession, so a hook can call a tool itself (used by the
    # side-effect hooks to trigger a re-render).
    session: Any = None

    # PRE_TOOL / POST_TOOL / TOOL_ERROR
    tool_name: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None

    # POST_TOOL: set by a handler that has already rendered for this call, so
    # later handlers in the same dispatch do not render a second time. One
    # HookContext is shared by every hook of a single dispatch, which makes this
    # naturally scoped to one tool call.
    handled: bool = False

    # TURN_START
    user_text: str = ""
    # Strings appended to the system prompt for this turn, in order.
    context_additions: List[str] = field(default_factory=list)

    # NO_TOOL_CALLS: what the model produced in the iteration that called nothing.
    assistant_text: str = ""
    thought_text: str = ""

    def add_context(self, text: str) -> None:
        """TURN_START only: contribute a block to this turn's system prompt."""
        if text:
            self.context_additions.append(text)

    def request_continuation(
        self, prompt: str, model_text: Optional[str] = None
    ) -> None:
        """NO_TOOL_CALLS only: ask for one more iteration.

        The engine appends `model_text` (defaulting to what the model just said)
        as the assistant turn and `prompt` as a synthetic user turn, then
        generates again. First hook to request wins.
        """
        if self.turn_state.get("continuation"):
            return
        self.turn_state["continuation"] = {
            "prompt": prompt,
            "model_text": model_text,
            "requested_by": self.event.value,
        }

    def abort_turn(self, reason: str) -> None:
        """Ask the ReAct loop to stop after the current iteration.

        The loop reports `reason` to the user rather than silently truncating.
        """
        self.turn_state["should_abort"] = True
        self.turn_state["abort_reason"] = reason


def new_turn_state(max_iterations: int) -> Dict[str, Any]:
    """Create the per-turn state dict with all keys hooks rely on present."""
    return {
        # Iteration accounting, so hooks (and the prompt) can reason about budget.
        "iteration": 0,
        "max_iterations": max_iterations,
        # fingerprint (tool + args) -> times called this turn. guard_repeat_call.
        "call_counts": {},
        # tool_name -> consecutive failures this turn. guard_consecutive_failures.
        "failure_counts": {},
        # Audit tallies surfaced at TURN_END.
        "tools_run": 0,
        "tools_blocked": 0,
        "tools_modified": 0,
        "tools_failed": 0,
        # Loop control.
        "should_abort": False,
        "abort_reason": None,
        # Set by request_continuation(); consumed and cleared by the loop.
        "continuation": None,
        # How many times a continuation has been granted, so a nudge cannot
        # ping-pong with the model for the whole iteration budget.
        "continuations_granted": 0,
        # Names of skills already loaded this turn, so TURN_START does not
        # re-suggest something the model already has in context.
        "skills_loaded": [],
    }
