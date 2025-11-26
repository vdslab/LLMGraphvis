# GraphVisAgent Knowledge Artifact

## 1. System Architecture

The system follows a **Microservices Architecture** with the following components:

- **Frontend (React)**: SPA for user interaction and graph visualization.
- **Backend (FastAPI)**: Orchestrator for business logic, authentication, and LLM interaction.
- **NetworkXAPI (FastAPI)**: Dedicated service for heavy graph calculations and rendering data generation.
- **Database (PostgreSQL)**: Persists user data, chat history, and graph data (nodes, edges, attributes).
- **LLM Service (Google Gemini)**: Interprets user intent and plans tool execution.

### Communication
- **Frontend <-> Backend**: REST API for actions, **Server-Sent Events (SSE)** for real-time updates (thinking process, tool execution, graph rendering).
- **Backend <-> NetworkXAPI**: REST API (synchronous calls, but often triggered by background tasks).
- **Backend <-> LLM**: REST API (Gemini).

## 2. Core Workflows

### 2.1. Unified Asynchronous Chat Flow
The system uses a unified async flow for all chat interactions to ensure responsiveness.

1.  **Request**: Frontend sends `POST /chat/{id}/process`.
2.  **Acceptance**: Backend saves message, returns `202 Accepted` immediately.
3.  **Background Processing**:
    - Backend sends context to LLM.
    - **Thinking Stream**: LLM's thought process is streamed to Frontend via SSE (`thinking_stream`).
    - **Tool Execution**: LLM decides to call tools. Backend executes them against NetworkXAPI and streams status (`tool_execution`).
    - **Iterative Process**: LLM may call multiple tools in sequence (e.g., `list_attributes` -> `calculate_centrality` -> `generate_visualization`).
4.  **Completion**:
    - **Render Update**: When `generate_visualization` completes, Backend sends `render_update` event with new graph data.
    - **Final Message**: Backend sends `message` event with LLM's final text response.

## 3. Data Models

### User
- `id`, `username`, `hashed_password`

### Chat
- `id`, `name`, `user_id`, `network_id`

### Network (Conceptual)
- Managed by NetworkXAPI and Database.
- Consists of `nodes`, `edges`, `node_attributes`, `edge_attributes`.
- Attributes are typed (float, string, etc.) and stored in separate tables.

## 4. LLM Tool Definitions

The LLM is provided with the following tools to manipulate the graph:

| Tool Name | Description | Key Parameters |
| :--- | :--- | :--- |
| `list_node_attributes` | List available node attributes. | None |
| `list_edge_attributes` | List available edge attributes. | None |
| `calculate_centrality` | Calculate centrality metrics. | `centrality_type` (degree, betweenness, etc.) |
| `calculate_layout` | Calculate node positions. | `layout_name` (spring, circular, etc.) |
| `generate_visualization` | Generate rendering data. | `layout_name`, `node_size_config`, `node_color_config`, etc. |

**Important Rule**: The LLM must `calculate_centrality` *before* using that metric in `generate_visualization`.

## 5. Implementation Status & Discrepancies

### 5.1. Consistency
- **Workflow**: The implementation in `chat.py` and `llm_service.py` aligns well with `6_Core_Workflows.md`.
- **Tools**: Tool definitions in `llm_service.py` match the endpoints in `tools.py`.

### 5.2. Unimplemented Features
- **None**: All core visualizer features (node coloring, edge styling) are now implemented.

### 5.3. Potential Issues (Readability & Logic)
- **Global Event Queues**: `llm_service.py` uses a global in-memory dictionary `event_queues` to manage SSE streams.
    - *Risk*: This will not work if the backend is scaled to multiple worker processes (e.g., using Gunicorn/Uvicorn with multiple workers) because memory is not shared.
    - *Recommendation*: Use Redis or a similar Pub/Sub system for production.
- **LLM Service Size**: `process_chat` in `llm_service.py` is large and mixes tool definitions with logic. Refactoring tool definitions into a separate module would improve readability.


