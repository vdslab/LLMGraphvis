from app.services.llm import markup


def test_persistent_blocks_use_markdown_directives():
    assert markup.steps_block(["Importing", "Rendering"]) == (
        ":::steps\nImporting\nRendering\n:::"
    )
    assert markup.collapsible("Details", "**Body**", open=True) == (
        ':::collapsible{title="Details" open="true"}\n**Body**\n:::'
    )
    assert markup.thought_block("Plan") == ":::thought\nPlan\n:::"
    assert markup.tool_execution_marker(3) == '::tool-execution{index="3"}'


def test_container_fence_cannot_be_closed_by_its_body():
    block = markup.thought_block("before\n:::\nafter")

    assert block.startswith("::::thought\n")
    assert block.endswith("\n::::")


def test_sanitize_model_output_removes_only_invented_visualization_markers():
    text = (
        "Done. <visualization_output network_id=\"42\" type=\"full\"/>\n"
        "`<div>` is still documentation."
    )

    assert markup.sanitize_model_output(text) == (
        "Done. \n`<div>` is still documentation."
    )
    assert markup.sanitize_model_output(
        "&lt;visualization-output network_id=\"42\"/&gt;Ready"
    ) == "Ready"


def test_sanitize_model_output_canonicalizes_textual_thinking_protocol():
    text = "<thought>\nPlan **carefully**\n</thought>\n\nDone."

    assert markup.sanitize_model_output(text) == (
        ":::thought\nPlan **carefully**\n:::\n\nDone."
    )
