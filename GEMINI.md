# Gemini Agent Instructions

This document contains rules and guidelines for the Gemini AI agent working on the GraphVisAgent project.

## 1. Specification Compliance Rules
- **Implementation Basis**: All implementations must be based on the documents in the `specification` directory.
- **Specification Updates**: If an implementation requires functionality not present in the `specification`, or deviates from it, **the specification must be modified** to reflect the actual implementation. Do not leave discrepancies between code and docs.

## 2. Development Guidelines

### 2.1. Adding New Tools
Tools are MCP tools, auto-discovered from decorated functions. There is **no**
schema to register by hand, and no `llm_service.py` (that file no longer exists).

1. Add the algorithm in `networkx-api/app/logic/`.
2. Add a `@mcp.tool()` + `@handle_tool_errors` function in
   `networkx-api/app/mcp/tools/{domain}/`, and export it from that package's
   `__init__.py`. The docstring and each `Field(description=...)` are sent to the
   model verbatim — write them as prompt text.
3. Restart the backend, or wait out `MCP_TOOLS_CACHE_TTL` (default 300s), so the
   backend re-discovers the tool list.
4. Only if the tool needs *procedural* guidance (when to reach for it, how to
   combine it): add or edit a skill in
   `backend/app/services/llm/skills/definitions/`. Do not add it to the system
   prompt — `prompts.py` holds only always-true policy.
5. Only if the tool needs *enforcement* (an argument to validate, a side effect
   to trigger): add a hook in `backend/app/services/llm/hooks/builtin/`.

### 2.2. Modifying Workflows
1. Update `specification/2_Technical_Details/6_Core_Workflows.md` first.
2. Update `chat.py`, `services/llm/service.py`, and `services/llm/engine.py`.
3. Update Frontend event listeners (`frontend/src/hooks/useChatConnection.js`).

## 3. General Behavior
- **Task Management**: Always use `task_boundary` to track progress.
- **Documentation**: Keep `knowledge.md` updated with the latest system architecture and status.
- **Code Quality**: Follow the existing patterns in the codebase (e.g., Service layer pattern, FastAPI best practices).
