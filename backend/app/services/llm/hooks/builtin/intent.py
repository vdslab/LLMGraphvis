"""NO_TOOL_CALLS hooks: recover from a turn that stopped short.

Two failure modes end a turn without finishing the work:

1. The model *says* it is about to do something and then stops, having called
   nothing ("次にコミュニティを計算します。" and then silence).
2. Tools ran but the model produced no closing text, so the user sees actions
   with no explanation.

Both were previously hardcoded in `_execute_tool_loop`. Case 1's detection was
English-only (`"will"` / `"let me"`), which never matched Japanese — the primary
UX language of this app, and the very case `prompts.py` calls out.

This remains a heuristic. It cannot be otherwise: distinguishing "I will now
compute X" from "I could compute X, shall I?" is a judgement about intent, and
the cost of a false positive (forcing an action the user did not approve, which
`conversation-flow` explicitly forbids) is higher than the cost of a false
negative (the user says "go ahead"). The suppression list below is therefore
deliberately broad, and only one nudge is granted per turn.
"""

import re
from typing import Optional

from app.core.logging import get_logger

from ..registry import hook
from ..types import HookContext, HookEvent

logger = get_logger(__name__)


# Phrases that state an intention to act. Matching is case-insensitive for the
# Latin patterns; Japanese has no case so those are literal.
_INTENT_PATTERNS = (
    # English
    r"\bi\s+will\b",
    r"\bi'?ll\b",
    r"\blet\s+me\b",
    r"\bi'?m\s+going\s+to\b",
    r"\bi\s+am\s+going\s+to\b",
    r"\bnow\s+i\b",
    r"\bnext,?\s+i\b",
    # Japanese: polite non-past ("...します") and its common inflections.
    r"します(?:ね)?[。\.]",
    r"していきます",
    r"してみます",
    r"いたします",
    r"進めます",
    r"次に",
    r"まず(?:は)?、",
)

# An action must be named too, so "I will explain the difference" does not fire.
_ACTION_PATTERNS = (
    # English
    r"visuali[sz]",
    r"calculat",
    r"comput",
    r"import",
    r"updat",
    r"chang",
    r"appl(?:y|ie)",
    r"colou?r",
    r"\bsize\b",
    r"layout",
    r"detect",
    r"extract",
    r"filter",
    r"creat",
    r"switch",
    r"render",
    # Japanese
    r"可視化",
    r"計算",
    r"適用",
    r"色分け",
    r"レイアウト",
    r"検出",
    r"抽出",
    r"フィルタ",
    r"作成",
    r"切り替",
    r"描画",
    r"更新",
    r"変更",
    r"サイズ",
    r"実行",
)

# If any of these appear, the model is asking the user rather than stalling.
# `conversation-flow` requires proposing options and waiting for approval, so
# these are frequent, legitimate turn endings and must never be overridden.
_QUESTION_PATTERNS = (
    r"[?？]",
    r"ますか",
    r"ですか",
    r"でしょうか",
    r"どちら",
    r"いずれ",
    r"よろしい",
    r"いかがで",
    r"教えてください",
    r"お知らせください",
    r"\bshall\s+i\b",
    r"\bwould\s+you\s+(?:like|prefer)\b",
    r"\bdo\s+you\s+want\b",
    r"\bwhich\b",
    r"\blet\s+me\s+know\b",
    r"\bplease\s+(?:tell|confirm|choose|specify)\b",
)


def _matches_any(text: str, patterns: tuple) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def detect_stalled_intent(text: str) -> bool:
    """True when `text` announces an action without asking anything."""
    if not text or not text.strip():
        return False
    if _matches_any(text, _QUESTION_PATTERNS):
        return False
    return _matches_any(text, _INTENT_PATTERNS) and _matches_any(text, _ACTION_PATTERNS)


MAX_CONTINUATIONS = 1


@hook(HookEvent.NO_TOOL_CALLS, priority=10, name="nudge_stalled_intent")
def nudge_stalled_intent(ctx: HookContext) -> None:
    """The model announced an action but called no tool: ask it to follow through."""
    if ctx.turn_state.get("continuations_granted", 0) >= MAX_CONTINUATIONS:
        return
    if not detect_stalled_intent(ctx.assistant_text):
        return

    logger.info(
        f"Stalled intent detected: '{ctx.assistant_text.strip()[:80]}...' — "
        f"requesting continuation"
    )
    ctx.request_continuation(
        prompt=(
            "You described an action but did not call the corresponding tool. "
            "Carry out that action now by calling the tool, in this same response."
        ),
        model_text=ctx.assistant_text or "I will now proceed.",
    )


@hook(HookEvent.NO_TOOL_CALLS, priority=20, name="force_final_summary")
def force_final_summary(ctx: HookContext) -> Optional[None]:
    """Tools ran but the model said nothing: make it report before the turn ends."""
    if ctx.turn_state.get("continuations_granted", 0) >= MAX_CONTINUATIONS:
        return None
    if ctx.turn_state.get("tools_run", 0) <= 0:
        return None
    if ctx.assistant_text.strip():
        return None

    logger.info("Tools executed but no final text produced — requesting summary")
    ctx.request_continuation(
        prompt=(
            "The actions have been completed. Please provide a concise final report "
            "summarizing what was done (e.g., 'Layout updated', 'Metrics calculated') "
            "and any relevant findings."
        ),
        model_text=(
            f"<thought>{ctx.thought_text}</thought>"
            if ctx.thought_text
            else "I have executed the tools."
        ),
    )
    return None
