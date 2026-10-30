"""Test-only entry point: real HTTP/MCP/DB/SSE, deterministic assistant replies.

Loaded only by docker-compose.test.yml; production never imports this module.
"""

from app.main import app  # noqa: F401
from app.services import chat_service, llm
from app.services.llm import emitters, events, mcp_client, tuning
from app.services.llm.markup import tool_execution_marker
from app.services.llm.providers.types import UsageData
from app.services.llm.tool_catalog import ToolCatalog
from common import models


async def scripted_reply(chat_id, user_message, db, **kwargs):
    chat = db.get(models.Chat, chat_id)
    queue = await events.get_event_queue(chat_id)
    catalog = ToolCatalog(await mcp_client.get_tools())
    state = {"network_id": chat.network_id, "executed_calls": []}
    catalog.initialize_turn(state)
    executions = []
    for name, arguments in [
        ("layout_spring", {"network_id": chat.network_id, "k": 0.5, "iterations": 50}),
        ("visualization_generate", {"network_id": chat.network_id}),
    ]:
        result = await mcp_client.execute_tool(name, arguments)
        call = {
            "name": name,
            "args": arguments,
            "result": result,
            "status": "completed",
        }
        state["executed_calls"].append(call)
        executions.append(call)
        if name == "visualization_generate":
            await emitters.emit_render_update(queue, result)
    panel = tuning.present_tuning(
        chat_id,
        db,
        {
            "question": "Spring spacing",
            "tools": ["layout_spring", "visualization_generate"],
            "fields": [
                {
                    "tool": "layout_spring",
                    "argument": "k",
                    "kind": "number",
                    "minimum": 0.1,
                    "maximum": 2,
                    "step": 0.1,
                    "suggested": 0.5,
                }
            ],
        },
        state,
    )
    if "error" in panel:
        raise RuntimeError(panel["error"])
    executions.append(
        {
            "name": "offer_parameter_tuning",
            "args": {},
            "result": panel,
            "status": "completed",
        }
    )
    text = "Regression ready. $x^2$\n\n" + tool_execution_marker(2)
    await emitters.emit_message_chunk(queue, text)
    return (
        text,
        [{"step_type": "tool_execution", "tool_calls": executions}],
        UsageData(),
        "lmstudio",
        "e2e-scripted",
    )


llm.process_chat = scripted_reply


async def skip_title(*args, **kwargs):
    return None


chat_service._maybe_autoname_chat = skip_title
