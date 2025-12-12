# Gemini Agent Instructions

This document contains rules and guidelines for the Gemini AI agent working on the GraphVisAgent project.

## 1. Specification Compliance Rules
- **Implementation Basis**: All implementations must be based on the documents in the `specification` directory.
- **Specification Updates**: If an implementation requires functionality not present in the `specification`, or deviates from it, **the specification must be modified** to reflect the actual implementation. Do not leave discrepancies between code and docs.

## 2. Development Guidelines

### 2.1. Adding New Tools
1. Define endpoint in `networkx-api/app/api/v1/endpoints/`.
2. Add logic in `networkx-api/app/logic/`.
3. Define tool schema in `backend/app/services/llm_service.py`.
4. Update `SYSTEM_INSTRUCTION` in `llm_service.py` if necessary.

### 2.2. Modifying Workflows
1. Update `specification/2_Technical_Details/6_Core_Workflows.md` first.
2. Update `chat.py` and `llm_service.py`.
3. Update Frontend event listeners.

## 3. General Behavior
- **Task Management**: Always use `task_boundary` to track progress.
- **Documentation**: Keep `knowledge.md` updated with the latest system architecture and status.
- **Code Quality**: Follow the existing patterns in the codebase (e.g., Service layer pattern, FastAPI best practices).
