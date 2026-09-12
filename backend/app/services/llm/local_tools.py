from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger
from .providers.types import ToolDefinition

logger = get_logger(__name__)


def _get_chat_and_network(chat_id: int, db: Session):
    """Helper to retrieve chat and its current network."""
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        return None, None, {"content": "Chat not found"}
        
    current_network = (
        db.query(models.Network)
        .filter(models.Network.id == chat.network_id)
        .first()
    )
    if not current_network:
        return chat, None, {"content": "Current network context not found"}
        
    return chat, current_network, None

async def switch_to_main_network(chat_id: int, db: Session) -> dict:
    """
    Switches the chat context back to the main (root) network.
    Use this when the user wants to go back to the original full graph.
    """
    try:
        chat, current_network, error_response = _get_chat_and_network(chat_id, db)
        if error_response:
            return error_response


        # Traverse up to find the root
        root_network = current_network
        while root_network.parent_network_id is not None:
            parent = (
                db.query(models.Network)
                .filter(models.Network.id == root_network.parent_network_id)
                .first()
            )
            if parent:
                root_network = parent
            else:
                break

        # Update chat context
        chat.network_id = root_network.id
        db.commit()

        return {"content": f"Context switched to Main Network (ID: {root_network.id})."}

    except Exception as e:
        logger.error(f"Error in switch_to_main_network: {e}")
        return {"content": f"Failed to switch to main network: {str(e)}"}


async def switch_to_parent_network(chat_id: int, db: Session) -> dict:
    """
    Switches the chat context to the parent network of the current subgraph.
    Use this when the user wants to go up one level in the hierarchy.
    """
    try:
        chat, current_network, error_response = _get_chat_and_network(chat_id, db)
        if error_response:
            return error_response


        if current_network.parent_network_id is None:
            return {
                "content": "Already at the top-level network. Cannot switch to parent."
            }

        # Update chat context
        chat.network_id = current_network.parent_network_id
        db.commit()

        return {
            "content": f"Context switched to Parent Network (ID: {current_network.parent_network_id})."
        }

    except Exception as e:
        logger.error(f"Error in switch_to_parent_network: {e}")
        return {"content": f"Failed to switch to parent network: {str(e)}"}


# What "activated" actually means, in the one place both tools read it from.
# `activated_tools` lists only the NEW names, so a second skill_load over an
# overlapping skill returns an empty list while those tools are in fact usable —
# `active_tools` is the key to read for "what can I call now".
ACTIVATION_NOTE = (
    "Scope: the rest of this turn. Activated tools stay callable in every later "
    "response of this turn, including after ask_user pauses for an answer. They "
    "are NOT callable in this same response — the current request's tool list was "
    "already fixed before this call ran. A new user message that does not answer "
    "a question starts a new turn and resets the set. `active_tools` is everything "
    "callable now; `activated_tools` is only what this call added."
)


async def skill_load(name: str, turn_state: dict) -> dict:
    """
    Loads the full text of a skill (a stored procedure for one kind of task).

    The system prompt lists only skill names and one-line descriptions; the
    procedures themselves are fetched through this tool so a turn only pays for
    what it actually needs.
    """
    from .skills import registry as skill_registry

    skill = skill_registry.get(name)
    if not skill:
        available = ", ".join(skill_registry.names()) or "(none)"
        return {
            "error": f"No skill named '{name}'. Available skills: {available}.",
        }

    loaded = turn_state.setdefault("skills_loaded", [])
    if skill.name not in loaded:
        loaded.append(skill.name)

    catalog = turn_state.get("tool_catalog")
    activated, missing = (
        catalog.activate(skill.related_tools, turn_state)
        if catalog is not None
        else ([], list(skill.related_tools))
    )

    logger.info(f"Skill loaded: {skill.name}")
    return {
        "skill": skill.name,
        "description": skill.description,
        "related_tools": skill.related_tools,
        "activated_tools": activated,
        "active_tools": catalog.active_names(turn_state) if catalog else [],
        "missing_tools": missing,
        "activation_note": ACTIVATION_NOTE,
        "content": skill.body,
    }


async def tool_search(query: str, limit: int, offset: int, turn_state: dict) -> dict:
    """Find and activate tool definitions from the per-turn catalogue."""
    query = str(query).strip()
    if not query:
        return {"error": "query must not be empty"}
    try:
        limit = min(max(int(limit), 1), 10)
        offset = max(int(offset), 0)
    except (TypeError, ValueError):
        return {"error": "limit and offset must be integers"}
    catalog = turn_state.get("tool_catalog")
    if catalog is None:
        return {"error": "The tool catalogue is not available for this turn."}

    matches = catalog.search(query)
    page = matches[offset : offset + limit]
    activated, _missing = catalog.activate((tool.name for tool in page), turn_state)
    turn_state["tool_searches"] = turn_state.get("tool_searches", 0) + 1
    return {
        "query": query,
        "results": [
            {
                "name": tool.name,
                "description": _short_description(tool.description),
            }
            for tool in page
        ],
        "activated_tools": activated,
        "active_tools": catalog.active_names(turn_state),
        "total": len(matches),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(page) < len(matches),
        "activation_note": ACTIVATION_NOTE,
    }


def _short_description(description: str, limit: int = 220) -> str:
    first = " ".join(description.strip().splitlines()).strip()
    if len(first) <= limit:
        return first
    return first[: limit - 1].rstrip() + "…"


def _skill_load_definition() -> ToolDefinition:
    """Build the tool schema, naming the real skills in the description.

    Enumerating them here means the model sees valid values in the schema
    itself, not only in the prompt's index block.
    """
    from .skills import registry as skill_registry

    names = skill_registry.names()
    listed = ", ".join(names) if names else "none loaded"
    return ToolDefinition(
        name="skill_load",
        description=(
            "Load the full procedure for a stored skill before carrying out that kind of "
            "task. Returns Markdown instructions you must then follow and activates the "
            "skill's related tool definitions for the rest of this turn — from your next "
            "response onward, and still after an ask_user answer. "
            f"Available skills: {listed}."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The skill name, exactly as listed in the Skills index.",
                    **({"enum": names} if names else {}),
                }
            },
            "required": ["name"],
        },
    )


def _tool_search_definition() -> ToolDefinition:
    return ToolDefinition(
        name="tool_search",
        description=(
            "Search the full tool catalogue and activate matching tool definitions for "
            "the rest of this turn, starting with your next response. Use this when no "
            "skill covers the operation, a needed "
            "tool is not currently visible, or a tool name from history must be loaded "
            "again. Search by capability, domain prefix, or exact tool name. Results "
            "contain short summaries rather than full schemas."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Non-empty capability, domain prefix, or exact tool name.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to activate, from 1 to 10. Defaults to 5.",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
                "offset": {
                    "type": "integer",
                    "description": "Zero-based result offset for pagination. Defaults to 0.",
                    "minimum": 0,
                    "default": 0,
                },
            },
            "required": ["query"],
        },
    )


def get_local_tools() -> list[ToolDefinition]:
    """Returns the list of local tools as provider-agnostic ToolDefinitions."""
    return [
        ToolDefinition(
            name="switch_to_main_network",
            description="Switches the chat context back to the main (root) network. Use this when the user wants to go back to the original full graph.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        ToolDefinition(
            name="switch_to_parent_network",
            description="Switches the chat context to the parent network of the current subgraph. Use this when the user wants to go up one level in the hierarchy.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        _skill_load_definition(),
        _tool_search_definition(),
        _input_definition(),
    ]


# Tools handled in-process rather than over MCP. The engine routes on this.
LOCAL_TOOL_NAMES = frozenset(
    {
        "switch_to_main_network",
        "switch_to_parent_network",
        "skill_load",
        "tool_search",
        "ask_user",
    }
)


def is_local_tool(tool_name: str) -> bool:
    return tool_name in LOCAL_TOOL_NAMES


async def execute_local_tool(tool_name: str, arguments: dict, context: dict):
    """Executes a local tool."""
    chat_id = context.get("chat_id")
    db = context.get("db")

    if tool_name == "ask_user":
        from .inputs import present_question
        return present_question(chat_id, db, arguments, context["turn_state"])
    if tool_name == "switch_to_main_network":
        return await switch_to_main_network(chat_id, db)
    elif tool_name == "switch_to_parent_network":
        return await switch_to_parent_network(chat_id, db)
    elif tool_name == "skill_load":
        return await skill_load(arguments.get("name", ""), context.get("turn_state") or {})
    elif tool_name == "tool_search":
        return await tool_search(
            arguments.get("query", ""),
            arguments.get("limit", 5),
            arguments.get("offset", 0),
            context.get("turn_state") or {},
        )
    else:
        raise ValueError(f"Unknown local tool: {tool_name}")


def _input_definition() -> ToolDefinition:
    """Build the ask_user schema from the Pydantic model that validates it.

    The schema goes through the same cleaner as an MCP tool's: a Pydantic
    rendering carries `$defs`, `title` keys and `exclusiveMinimum`, and
    `google.genai.types.Schema` rejects the last of those outright — which
    failed the whole request, not just this tool, because `ask_user` is in
    the initial exposure set.
    """
    from .inputs import InputForm
    from .mcp_client import _resolve_schema_refs, _sanitize_schema

    schema = InputForm.model_json_schema()
    schema = _sanitize_schema(_resolve_schema_refs(schema, schema))

    return ToolDefinition(
        name="ask_user",
        description=(
            "REQUIRED when asking the user to choose among distinct alternatives (e.g. 'what analyses are possible?'). "
            "Plain text lists do not display interactive UI controls. The parameter schema defines the shape of "
            "`fields`; these are the rules the schema cannot state.\n\n"
            "1. Explain in the SAME response: Write ordinary text explaining what each option would show and which visual "
            "channels it assigns. A turn containing only this form gives the user a menu with nothing to judge it by.\n"
            "2. One question, one field: alternative views or goals go in a single select field with 2–4 options, never "
            "one field per candidate and never split across categories. Do not add a separate free-text field — "
            "selection controls get Other/free-text from the UI.\n"
            "3. Language: Use the conversation language (e.g. Japanese) for question, labels, and options. Keep technical "
            "IDs and values unchanged.\n"
            "4. Turn boundary: This ends the turn and waits for an answer. Call it alone: other calls in the same batch are "
            "deferred. The tools you have activated stay available in the turn that handles the answer. Do not use for "
            "direct instructions, refinements of what is on screen, questions you can answer yourself, "
            "or things already specified. Free-text replies are accepted; treat partial answers ('any', 'you choose') as "
            "valid decisions rather than re-asking. No analysis or view change occurs."
        ),
        parameters=schema,
    )
