"""Persistent Markdown directives understood by the chat renderer.

A persisted chat message is a single Markdown string, so anything that is not
prose is marked up inside it. The frontend parses these directives in
`frontend/src/utils/parseMessageContent.js`; the two files are one contract and
change together.

Directives produced here:

- `:::steps`       a fixed pipeline log (one step per line). Rendered as a
                   collapsed checklist labelled "Steps".
- `:::collapsible` a section the user can fold away. Used for the upload
                   overview, which is long and read once.

`:::thought` is only produced through `thought_block`, which the engine uses
around model reasoning. It is the one block the "Thinking" heading may describe.
"""

import re

STEPS_DIRECTIVE = "steps"
COLLAPSIBLE_DIRECTIVE = "collapsible"

_UNSUPPORTED_VISUALIZATION_TAG = re.compile(
    r"(?:<|&lt;)\s*visualization[_-]output\b[\s\S]*?(?:/?>|/?&gt;)",
    re.IGNORECASE,
)
_LEGACY_THOUGHT_BLOCK = re.compile(
    r"(?:<|&lt;)\s*thought\s*(?:>|&gt;)([\s\S]*?)"
    r"(?:(?:<|&lt;)\s*/\s*thought\s*(?:>|&gt;)|$)",
    re.IGNORECASE,
)
_MODEL_AUTHORED_TOOL_MARKER = re.compile(
    r"(?m)^[ \t]*::tool-execution\{[^}\n]*\}[ \t]*(?:\n|$)",
    re.IGNORECASE,
)


def _container_directive(name: str, body: str, attributes: str = "") -> str:
    """Wrap Markdown in a container directive with a collision-safe fence."""
    colon_runs = [len(match.group(0)) for match in re.finditer(r"(?m)^:+", body)]
    fence = ":" * max(3, max(colon_runs, default=0) + 1)
    return f"{fence}{name}{attributes}\n{body}\n{fence}"


def thought_block(body: str) -> str:
    """Wrap model reasoning in the one directive rendered as Thinking."""
    return _container_directive("thought", body)


def tool_execution_marker(index: int) -> str:
    """Mark where a persisted tool execution belongs in the transcript."""
    return f'::tool-execution{{index="{index}"}}'


def sanitize_model_output(text: str) -> str:
    """Canonicalize reserved model markup before display and persistence.

    Visualization delivery is an SSE event, never message markup. Restrict the
    filter to that exact reserved-looking name so legitimate HTML examples are
    left untouched. Textual-thinking providers still emit the legacy tag as
    their wire protocol; convert it to the persisted Markdown directive here.
    """
    without_visualization_tags = _UNSUPPORTED_VISUALIZATION_TAG.sub("", text)
    return _LEGACY_THOUGHT_BLOCK.sub(
        lambda match: thought_block(match.group(1).strip()),
        without_visualization_tags,
    )


_THOUGHT_DIRECTIVE_BLOCK = re.compile(
    r"(?m)^(:{3,})thought\b[\s\S]*?(?:^\1[ \t]*$|\Z)"
)


def visible_text(text: str) -> str:
    """What the model actually said to the user, with reasoning stripped.

    Providers without a native thinking stream write their reasoning as
    `<thought>` tags inside the ordinary text channel, so the raw text is not a
    usable answer to "has the model addressed the user yet?" — a turn made
    entirely of reasoning looks like prose to a naive length check.
    """
    without_thoughts = _LEGACY_THOUGHT_BLOCK.sub("", text)
    without_thoughts = _THOUGHT_DIRECTIVE_BLOCK.sub("", without_thoughts)
    return _MODEL_AUTHORED_TOOL_MARKER.sub("", without_thoughts).strip()


# Gemini sometimes writes a function call in its code-execution text format
# instead of calling it: a `tool_code` block (as a fence, or a `::tool_code`
# line copied from our `::tool-execution` markers) of `print(default_api.f(...))`
# lines. Text is never executed, so such a block only misleads the reader.
_TEXTUAL_TOOL_CALL_FENCE = re.compile(
    r"(?ms)^[ \t]*```[ \t]*tool[_-]code[ \t]*\n.*?(?:^[ \t]*```[ \t]*(?:\n|\Z)|\Z)",
    re.IGNORECASE,
)
# A line that is only `tool_code`; the block runs until the first blank line.
_TEXTUAL_TOOL_CALL_BLOCK = re.compile(
    r"(?m)^[ \t]*:*[ \t]*tool[_-]code[ \t]*(?:\n|\Z)(?:[ \t]*\S[^\n]*(?:\n|\Z))*",
    re.IGNORECASE,
)
_TEXTUAL_TOOL_CALL_LINE = re.compile(
    r"(?m)^[ \t]*(?:print\(\s*)?default_api\.\w+\([^\n]*(?:\n|\Z)"
)
_TEXTUAL_TOOL_CALL_NAME = re.compile(r"default_api\.(\w+)\(")


def split_textual_tool_calls(text: str) -> tuple[str, list[str]]:
    """Remove tool calls written as text; return the rest and the tools named.

    The names are in order of appearance, repeats kept. A block that names no
    tool is still removed: `tool_code` is never prose meant for the user.
    """
    names: list[str] = []

    def remove(match: re.Match) -> str:
        names.extend(_TEXTUAL_TOOL_CALL_NAME.findall(match.group(0)))
        return ""

    for pattern in (
        _TEXTUAL_TOOL_CALL_FENCE,
        _TEXTUAL_TOOL_CALL_BLOCK,
        _TEXTUAL_TOOL_CALL_LINE,
    ):
        text = pattern.sub(remove, text)
    return text, names


def sanitize_model_text(text: str) -> str:
    """Remove engine-owned control markers copied into a model text part."""
    text = _UNSUPPORTED_VISUALIZATION_TAG.sub("", text)
    text, _names = split_textual_tool_calls(text)
    return _MODEL_AUTHORED_TOOL_MARKER.sub("", text)


def history_text(content: str) -> str:
    """A stored reply as the model should see it in a later turn's history.

    The tool calls of a past turn are replayed as real function-call parts, so
    the `::tool-execution` markers that place them in the chat panel carry
    nothing for the model. Left in, a reply made only of markers teaches it to
    answer with directive lines, which is how `::tool_code` text first appeared.
    A reply that leaked tool calls as text is cleaned for the same reason.
    """
    text = _MODEL_AUTHORED_TOOL_MARKER.sub("", content)
    text, _names = split_textual_tool_calls(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def steps_block(steps: list[str]) -> str:
    """Wrap completed pipeline steps as a collapsed checklist."""
    if not steps:
        return ""
    body = "\n".join(steps)
    return _container_directive(STEPS_DIRECTIVE, body)


def collapsible(title: str, body: str, *, open: bool = False) -> str:
    """Wrap `body` in a section folded behind `title`.

    `title` is plain text — it lands in an attribute, so it must not contain a
    double quote or a newline.
    """
    if not body:
        return ""
    safe_title = title.replace('"', "'").replace("\n", " ")
    attrs = f'{{title="{safe_title}"'
    if open:
        attrs += ' open="true"'
    attrs += "}"
    return _container_directive(COLLAPSIBLE_DIRECTIVE, body, attrs)
