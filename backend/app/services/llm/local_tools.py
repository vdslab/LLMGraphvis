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
        "missing_tools": missing,
        "activation_note": (
            "Activated tools are available from the next model response."
        ),
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
        "total": len(matches),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(page) < len(matches),
        "activation_note": "Results are available from the next model response.",
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
            "skill's related tool definitions for your next response. "
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
            "the next response. Use this when no skill covers the operation, a needed "
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
    from .inputs import InputForm

    schema = InputForm.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(value):
        if isinstance(value, list):
            return [inline(item) for item in value]
        if isinstance(value, dict):
            if "$ref" in value:
                return inline(definitions[value["$ref"].split("/")[-1]])
            return {key: inline(item) for key, item in value.items()}
        return value

    return ToolDefinition(
        name="ask_user",
        description=(
            "REQUIRED when asking the user to choose among distinct alternatives (e.g. 'what analyses are possible?'). "
            "Plain text lists do not display interactive UI controls.\n\n"
            "Key Rules:\n"
            "1. Explain in the SAME response: Write ordinary text explaining what each option would show and which visual "
            "channels it assigns. A turn containing only this form gives the user a menu with nothing to judge it by.\n"
            "2. Single select field for goals: When offering alternative views or goals, create exactly ONE select field "
            "with 2–4 options. Put all candidates in its 'options' list; never create multiple fields with one option each, "
            "and do not split choices across categories.\n"
            "3. Field keys: Use id, label, kind (never use 'title'). Options require 2–12 distinct items. Other/free-text "
            "is added automatically (allow_other defaults true), so do not add 'Other' as an option. Sliders require finite "
            "minimum/maximum.\n"
            "4. Language: Use the conversation language (e.g. Japanese) for question, labels, and options. Keep technical "
            "IDs and values unchanged.\n"
            "5. Turn boundary: This ends the turn and waits for an answer. Call it alone: other calls in the same batch are "
            "deferred. Do not use for direct instructions, refinements of what is on screen, questions you can answer yourself, "
            "or things already specified. Free-text replies are accepted; treat partial answers ('any', 'you choose') as "
            "valid decisions rather than re-asking. No analysis or view change occurs."
        ),
        parameters=inline(schema),
    )
