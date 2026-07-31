"""In-band markup understood by the chat renderer.

A persisted chat message is a single Markdown string, so anything that is not
prose is marked up inside it. The frontend splits a message on these tags in
`frontend/src/utils/parseMessageContent.js`; the two files are one contract and
change together.

Tags produced here:

- `<steps>…</steps>`      a fixed pipeline log (one step per line). Rendered as
                          a collapsed checklist labelled "Steps".
- `<collapsible title=…>` a section the user can fold away. Used for the upload
                          overview, which is long and read once.

`<thought>` is *not* here on purpose. It is written by the engine around model
reasoning only (see engine.py) and is the one block the "Thinking" heading may
describe — labelling our own progress log as thinking is what this module
exists to avoid.
"""

STEPS_TAG = "steps"
COLLAPSIBLE_TAG = "collapsible"


def steps_block(steps: list[str]) -> str:
    """Wrap completed pipeline steps as a collapsed checklist."""
    if not steps:
        return ""
    body = "\n".join(steps)
    return f"<{STEPS_TAG}>{body}</{STEPS_TAG}>"


def collapsible(title: str, body: str, *, open: bool = False) -> str:
    """Wrap `body` in a section folded behind `title`.

    `title` is plain text — it lands in an attribute, so it must not contain a
    double quote or a newline.
    """
    if not body:
        return ""
    safe_title = title.replace('"', "'").replace("\n", " ")
    attrs = f' title="{safe_title}"'
    if open:
        attrs += ' open="true"'
    return f"<{COLLAPSIBLE_TAG}{attrs}>\n{body}\n</{COLLAPSIBLE_TAG}>"
