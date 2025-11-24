# GraphVisAgent Knowledge Base

## 1. Project Overview
GraphVisAgent is a conversational network analysis and visualization platform. It allows users to upload GraphML files and interact with the network using natural language commands. The system leverages Large Language Models (LLM) to interpret user requests and orchestrate network analysis tools (NetworkX) to dynamically update the visualization.

## 2. Architecture
The system follows a microservices architecture with the following containers:

- **Frontend (React/Vite)**: SPA for user interface.
- **Backend (FastAPI)**: Orchestrates LLM and NetworkXAPI, manages authentication and chat history.
- **NetworkXAPI (FastAPI)**: Handles heavy network calculations (layout, centrality) and generates rendering data.
- **Database (PostgreSQL)**: Persists users, chats, networks, and calculated attributes.
- **LLM Service (External)**: Google Gemini 2.5 Flash for natural language understanding and tool planning.

### Communication
- **Frontend <-> Backend**: REST API for actions, Server-Sent Events (SSE) for real-time updates (rendering, thinking process).
- **Backend <-> NetworkXAPI**: REST API (synchronous/asynchronous).

## 3. Specifications vs Implementation

### Backend (`backend/`)
- **Implemented Endpoints**:
    - `/auth`: Register, Token, Me.
    - `/chat`: List, Create, Get, Upload, Process, Stream, Export.
- **LLM Service (`llm_service.py`)**:
    - Implements `process_chat` with Gemini Function Calling.
    - Tools: `list_attributes`, `calculate_centrality`, `calculate_layout`, `create_visualization`.
    - **Note**: The tool name `create_visualization` in LLM maps to `generate_visualization` in NetworkXAPI.
    - **Context Retention**: System instructions explicitly direct the LLM to maintain visualization state (layout, node size/color) from previous turns unless explicitly changed.

### Frontend (`frontend/`)
- **Implemented Pages**:
    - `HomePage`, `LoginPage`, `RegisterPage`, `NetworkChatPage`.
- **Stores (Zustand)**:
    - `authStore`: Authentication state.
    - `chatStore`: Chat history and SSE handling.
    - `networkStore`: Visualization data (`nodes`, `links`).
- **Components**:
    - `NetworkGraph`: D3.js based visualization.
    - `ChatInterface`: Chat UI.

### NetworkXAPI (`networkx-api/`)
- **Implemented Endpoints (`/tools`)**:
    - `initialize_network`: Parses GraphML, saves to DB, calculates initial layout.
    - `list_attributes`: Lists available node attributes.
    - `calculate_centrality`: Calculates and saves centrality metrics.
    - `calculate_layout`: Calculates and saves layout coordinates.
    - `generate_visualization`: Generates final rendering data based on config.

### Discrepancies & Notes
- **Layout Calculation**: The specification mentions `calculate_layout` as a separate step. The implementation in `llm_service.py` and `NetworkXAPI` supports this.
- **Visualization Generation**: The `generate_visualization` endpoint in NetworkXAPI does *not* calculate layout on the fly; it uses pre-calculated or default layouts. This matches the "Stateless" design goal.
- **Tool Naming**: LLM tool `create_visualization` corresponds to `generate_visualization` in the backend/NetworkXAPI logic.

## 4. Core Workflows

### 4.1. New Chat & Initialization
1.  **User**: Creates new chat -> `POST /chat`.
2.  **User**: Uploads GraphML -> `POST /chat/{id}/upload`.
3.  **Backend**: Accepts upload (202 Accepted), starts background task.
4.  **Backend (Background)**: Calls `NetworkXAPI.initialize_network`.
5.  **NetworkXAPI**: Parses, saves to DB, calculates Spring layout.
6.  **Backend**: Receives initial data, broadcasts `render_update` via SSE.
7.  **Frontend**: Receives SSE, updates `networkStore`, renders graph.

### 4.2. Chat & Visualization Update
1.  **User**: Sends message (e.g., "Show popular nodes") -> `POST /chat/{id}/process`.
2.  **Backend**: Saves message, returns 202 Accepted, starts background task.
3.  **Backend (Background)**: Calls LLM with history and tools.
4.  **LLM**: Decides to call tools (e.g., `calculate_centrality`, then `create_visualization`).
5.  **Backend**: Executes tools against `NetworkXAPI`.
    - `calculate_centrality`: NetworkXAPI computes and saves to DB.
    - `create_visualization`: NetworkXAPI reads from DB and generates JSON.
6.  **Backend**: Streams tool execution status and final `render_update` via SSE.
7.  **Frontend**: Updates graph based on `render_update`.

## 5. Data Models

### User
- `id`, `username`, `hashed_password`

### Chat
- `id`, `name`, `user_id`, `network_id`

### Network (DB)
- `id`, `name`
- Related tables: `nodes`, `edges`, `node_attributes`, `node_attribute_values`

### Visualization Data (JSON)
```json
{
  "nodes": [
    { "id": "n1", "label": "Node 1", "x": 0.1, "y": 0.2, "size": 10, "color": "#ff0000" }
  ],
  "links": [
    { "source": "n1", "target": "n2", "width": 1, "color": "#cccccc" }
  ]
}
```

## 6. Configuration
### Environment Variables
- **Backend**:
    - `GOOGLE_API_KEY`: Required for Gemini API access.
    - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`: Database connection details.
- **NetworkXAPI**:
    - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`: Database connection details.

## 7. LLM Tools Definition

| Tool Name | Description | Parameters |
| :--- | :--- | :--- |
| `list_attributes` | List available node attributes. | None |
| `calculate_centrality` | Calculate centrality metrics. | `centrality_type` (degree, betweenness, etc.) |
| `calculate_layout` | Calculate node positions. | `layout_name` (spring, circular, etc.) |
| `create_visualization` | Generate visualization data. | `layout_name`, `node_size_config`, `node_color_config` |

## 8. Implementation Status
- **Backend**: Fully implemented core logic, SSE, and LLM integration.
- **Frontend**: Implemented D3 visualization, Chat UI, and SSE connection.
- **NetworkXAPI**: Implemented core graph processing and attribute management.
- **Verification**: 
    - `verify_create_vis_flow.py`: **Primary verification script**. Verifies the visualization flow (`calculate_centrality` -> `calculate_layout` -> `create_visualization`).
    - `verify_llm_flow.py`: Legacy script, checks for `update_visualization` (deprecated tool name). Needs update.
