"""Automatic chat titles.

A chat is created as "New Chat". Two things can rename it, in order, and both
stop at the first sign of a human decision (``Chat.name_is_custom``):

1. the uploaded GraphML filename, as an immediate provisional name;
2. a short LLM-generated title, once, after the first exchange.

The title call is a plain one-shot generation with no tools: it must never
touch the graph, so it does not go through the ReAct engine.
"""
import re
from typing import Optional

from app.core.logging import get_logger

from .engine import create_provider
from .providers.types import LLMMessage, LLMTextPart

logger = get_logger(__name__)

# Titles longer than this are cut — the chat list shows one ellipsized line.
MAX_TITLE_LENGTH = 40

# Names that mean "nobody has named this yet". Compared case-insensitively.
PLACEHOLDER_NAMES = {
    "",
    "new chat",
    "untitled",
    "untitled chat",
    "新しいチャット",
    "無題",
}

TITLE_SYSTEM_INSTRUCTION = (
    "You name chat threads in a network-visualization tool. "
    "Given the first exchange of a conversation, reply with a title for it "
    "and nothing else.\n"
    "Rules:\n"
    f"- At most {MAX_TITLE_LENGTH} characters.\n"
    "- Write it in the same language the user wrote in.\n"
    "- Name what the user is analysing (the data and the question), "
    "not the tool or the assistant.\n"
    "- No quotes, no trailing punctuation, no prefix such as 'Title:'."
)


def is_placeholder_name(name: Optional[str]) -> bool:
    """Whether this name is a not-yet-named default rather than a real title."""
    return (name or "").strip().lower() in PLACEHOLDER_NAMES


def name_from_filename(filename: Optional[str]) -> Optional[str]:
    """Turn an uploaded filename into a provisional chat name.

    "karate_club.graphml" -> "karate club". Returns None if nothing usable is
    left, so the caller can leave the placeholder in place.
    """
    if not filename:
        return None

    # Strip any directory part a browser may have included, then the extension.
    stem = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = re.sub(r"\.(graphml|xml|gml)$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_]+", " ", stem).strip()

    if not stem or is_placeholder_name(stem):
        return None
    return stem[:MAX_TITLE_LENGTH]


def _clean_title(raw: str) -> Optional[str]:
    """Reduce a model reply to a single short line, or None if unusable."""
    title = (raw or "").strip()
    if not title:
        return None

    # Models occasionally wrap the answer in a fence or offer alternatives on
    # further lines; keep the first non-empty line only.
    title = title.strip("`").strip()
    for line in title.splitlines():
        line = line.strip()
        if line:
            title = line
            break
    else:
        return None

    title = re.sub(r"^(title|タイトル)\s*[:：]\s*", "", title, flags=re.IGNORECASE)
    title = title.strip().strip("\"'“”「」『』").strip()
    title = title.rstrip("。．.、,!！?？")

    if not title or is_placeholder_name(title):
        return None
    return title[:MAX_TITLE_LENGTH]


async def generate_chat_title(
    user_message: str,
    assistant_message: str,
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    current_name: Optional[str] = None,
) -> Optional[str]:
    """Ask the LLM for a title for this chat, or return None if it can't.

    Failures are logged and swallowed: a chat keeping its placeholder name is a
    cosmetic problem, and must never break the turn that triggered the naming.
    """
    if not (user_message or "").strip():
        return None

    prompt_parts = []
    if current_name and not is_placeholder_name(current_name):
        # After an upload the chat is already named after the file; that name is
        # usually the dataset, which is worth keeping in the title.
        prompt_parts.append(f"Dataset: {current_name}")
    prompt_parts.append(f"User: {user_message.strip()[:2000]}")
    if (assistant_message or "").strip():
        prompt_parts.append(f"Assistant: {assistant_message.strip()[:2000]}")

    history = [
        LLMMessage(role="user", parts=[LLMTextPart(text="\n\n".join(prompt_parts))])
    ]

    try:
        provider = create_provider(provider_name, model_name)
        text = ""
        async for chunk in provider.generate(history, [], TITLE_SYSTEM_INSTRUCTION):
            if chunk.text:
                text += chunk.text
    except Exception as e:
        logger.warning(f"Chat title generation failed: {e}")
        return None

    title = _clean_title(text)
    if not title:
        logger.warning(f"Chat title generation returned nothing usable: {text!r}")
    return title
