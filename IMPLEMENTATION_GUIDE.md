# GraphVisAgent - Complete Implementation Guide

## Overview

This guide documents the complete implementation of the GraphVisAgent system with Gemini API integration for natural language-based network visualization.

## Architecture

The system consists of three main services:

1. **Backend (FastAPI)** - Main API service with authentication and LLM integration
2. **NetworkX API (FastAPI)** - Network analysis and visualization service
3. **Frontend (React + Vite)** - User interface

## Key Features Implemented

### 1. Authentication System
- User registration and login with JWT tokens
- Cookie-based authentication for browser clients
- Token-based authentication for API clients
- Protected routes and SSE streams

### 2. GraphML Upload Flow
- Asynchronous file upload (202 Accepted pattern)
- Background processing via NetworkX API
- Real-time updates via Server-Sent Events (SSE)
- Initial network visualization with default layout

### 3. LLM-Powered Chat Interface
- **Gemini API Integration** using `google-genai` SDK
- **Function Calling** for network operations
- **Streaming responses** via SSE
- **Tool execution tracking** with status updates

### 4. Network Visualization Tools

The LLM has access to three main tools:

#### `list_attributes(network_id: int)`
Lists all available node attributes in the network.

#### `calculate_centrality(network_id: int, centrality_type: str)`
Calculates centrality metrics:
- `degree` - Degree centrality (number of connections)
- `betweenness` - Betweenness centrality (bridge nodes)
- `closeness` - Closeness centrality
- `eigenvector` - Eigenvector centrality (influence)

#### `generate_visualization(network_id, layout_name, node_size_attribute, ...)`
Generates visualization with custom mappings:
- Layout algorithms (spring, circular, etc.)
- Node size mapping to attributes
- Node color mapping to attributes

## Complete User Flow

### 1. Login/Register
```
User → Frontend → POST /api/auth/register
                → POST /api/auth/token
```

### 2. Create Chat
```
User → Frontend → POST /api/chat
                ← { id, network_id, ... }
```

### 3. Upload GraphML
```
User → Frontend → POST /api/chat/{id}/upload (file)
                ← 202 Accepted

Backend → NetworkX API → POST /tools/initialize_network
                        ← { nodes, links }

Backend → SSE → render_update event
              → system_message event
```

### 4. Chat Interaction
```
User: "友達が多い人を大きく表示して"
     (Show people with many friends as larger)

Frontend → POST /api/chat/{id}/process
        ← 202 Accepted

Backend → Gemini API (with function calling)
        → LLM decides to:
          1. calculate_centrality(network_id, "degree")
          2. generate_visualization(node_size_attribute="degree_centrality")

Backend → SSE Events:
        → thinking_stream: "Analyzing your request..."
        → tool_execution: { tool: "calculate_centrality", status: "started" }
        → thinking_stream: "Calculating degree centrality..."
        → tool_execution: { tool: "calculate_centrality", status: "completed" }
        → tool_execution: { tool: "generate_visualization", status: "started" }
        → thinking_stream: "Generating visualization..."
        → render_update: { nodes: [...], links: [...] }
        → tool_execution: { tool: "generate_visualization", status: "completed" }
        → message: { role: "assistant", content: "I've updated..." }
```

## SSE Event Types

The system uses Server-Sent Events for real-time updates:

### `render_update`
```json
{
  "event": "render_update",
  "data": {
    "nodes": [
      { "id": "1", "x": 0.5, "y": 0.3, "size": 15, "color": "#4CAF50" }
    ],
    "links": [
      { "source": "1", "target": "2" }
    ]
  }
}
```

### `thinking_stream`
```json
{
  "event": "thinking_stream",
  "data": { "content": "Calculating degree centrality..." }
}
```

### `tool_execution`
```json
{
  "event": "tool_execution",
  "data": {
    "tool": "calculate_centrality",
    "status": "started|completed|failed",
    "args": { "centrality_type": "degree" },
    "error": "error message if failed"
  }
}
```

### `message`
```json
{
  "event": "message",
  "data": {
    "role": "assistant",
    "content": "I've updated the visualization...",
    "id": 123,
    "created_at": "2025-11-19T12:00:00"
  }
}
```

### `system_message`
```json
{
  "event": "system_message",
  "data": { "content": "Graph uploaded successfully." }
}
```

### `error`
```json
{
  "event": "error",
  "data": "Error message"
}
```

## Gemini API Implementation Details

### SDK Used
```python
from google import genai
from google.genai import types
```

**Important:** We use the **Google GenAI SDK** (`google-genai`), NOT the legacy `google-generativeai` library.

### Model Used
We use **Gemini 2.5 Flash** (`gemini-2.5-flash`) for optimal performance and function calling support.

### Client Initialization
```python
client = genai.Client(api_key=GOOGLE_API_KEY)
```

### Function Calling Pattern
```python
# Define tools as Python functions
def calculate_centrality(network_id: int, centrality_type: str) -> Dict[str, Any]:
    """Calculate centrality metrics..."""
    pass

# Call Gemini with tools
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=history,
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[list_attributes, calculate_centrality, generate_visualization],
        temperature=0.7,
    )
)

# Process function calls
if response.candidates[0].content.parts:
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'function_call') and part.function_call:
            function_call = part.function_call
            # Execute the function
            result = await execute_tool(function_call.name, dict(function_call.args))
            
            # Continue conversation with result
            history.append(response.candidates[0].content)
            history.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(
                    name=function_call.name,
                    response=result
                )]
            ))
```

## Known Limitations & Technical Debt

### Global Event Queues
`llm_service.py` uses a global in-memory dictionary `event_queues` to manage SSE streams.
- **Risk**: This will not work if the backend is scaled to multiple worker processes (e.g., using Gunicorn/Uvicorn with multiple workers) because memory is not shared.
- **Recommendation**: Use Redis or a similar Pub/Sub system for production.

### LLM Service Size
`process_chat` in `llm_service.py` is large and mixes tool definitions with logic. Refactoring tool definitions into a separate module would improve readability.

## Testing

### Prerequisites
1. Start all services:
```bash
docker compose up -d
```

2. Set environment variables:
```bash
export GOOGLE_API_KEY="your-api-key-here"
```

### Automated Test
```bash
python test_complete_flow.py
```

This will:
1. Register a new user
2. Create a chat
3. Upload the karate club network
4. Send a message to visualize by degree centrality
5. Verify the response

### Manual Testing

1. **Open the frontend**: http://localhost:5173

2. **Register/Login**:
   - Click "Register" or "Login"
   - Enter credentials

3. **Create a new chat**:
   - Click "New Chat"
   - Enter a name

4. **Upload GraphML**:
   - Click "Upload GraphML"
   - Select a file from `sample_data/`

5. **Chat with the system**:
   - "友達が多い人を大きく表示して" (Show people with many friends larger)
   - "橋渡しをしている人を大きく表示して" (Show bridge nodes larger)
   - "影響力のある人を大きく表示して" (Show influential people larger)

### Example Queries

**English:**
- "Show people with many friends as larger"
- "Highlight bridge nodes"
- "Show influential nodes with larger size"
- "Color nodes by community"

**Japanese:**
- "友達が多い人を大きく表示して"
- "橋渡しをしている人を大きく表示して"
- "影響力のある人を大きく表示して"

## File Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   ├── auth.py          # Authentication endpoints
│   │   └── chat.py          # Chat and upload endpoints
│   ├── services/
│   │   ├── llm_service.py   # Gemini API integration
│   │   └── network_service.py # NetworkXAPI client
│   └── ...

frontend/
├── src/
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── RegisterPage.jsx
│   │   └── NetworkChatPage.jsx  # Main chat interface
│   ├── components/
│   │   ├── ChatInterface.jsx
│   │   └── NetworkGraph.jsx
│   ├── stores/
│   │   ├── authStore.js
│   │   ├── chatStore.js
│   │   └── networkStore.js
│   └── ...

networkx-api/
├── app/
│   ├── api/v1/endpoints/
│   │   └── tools.py          # Network analysis tools
│   ├── logic/
│   │   ├── graph_processor.py
│   │   └── visualizer.py
│   └── ...
```

## Environment Variables

### Backend
```env
GOOGLE_API_KEY=your-gemini-api-key
DATABASE_URL=postgresql://user:pass@db:5432/graphvisagent
SECRET_KEY=your-secret-key
NETWORKX_API_URL=http://networkx-api:8001
```

### Frontend
```env
VITE_API_URL=http://localhost:8000
```

## Troubleshooting

### SSE Connection Issues
- Check browser console for errors
- Verify authentication token is valid
- Check backend logs for SSE errors

### LLM Not Responding
- Verify `GOOGLE_API_KEY` is set correctly
- Check backend logs for Gemini API errors
- Ensure network has been uploaded first

### Upload Fails
- Check file is valid GraphML format
- Verify NetworkX API is running
- Check backend logs for processing errors

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/token` - Login
- `GET /api/auth/users/me` - Get current user
- `POST /api/auth/logout` - Logout

### Chat
- `GET /api/chat` - List all chats
- `POST /api/chat` - Create new chat
- `GET /api/chat/{id}` - Get chat details
- `GET /api/chat/{id}/messages` - Get chat messages
- `POST /api/chat/{id}/upload` - Upload GraphML (202 Accepted)
- `POST /api/chat/{id}/process` - Process message (202 Accepted)
- `GET /api/chat/{id}/stream` - SSE stream
- `GET /api/chat/{id}/export` - Export as GraphML

### NetworkX API Tools
- `POST /tools/initialize_network` - Parse and initialize network
- `GET /tools/list_attributes` - List node attributes
- `POST /tools/calculate_centrality` - Calculate centrality
- `POST /tools/generate_visualization` - Generate visualization

## Next Steps

1. **Add more centrality types**: PageRank, Katz, etc.
2. **Community detection**: Louvain, Label Propagation
3. **Layout algorithms**: Force-directed, hierarchical, etc.
4. **Export options**: PNG, SVG, PDF
5. **Collaborative features**: Share chats, real-time collaboration
6. **Advanced queries**: Complex multi-step analysis

## References

- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
- [Google GenAI SDK](https://ai.google.dev/gemini-api/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [NetworkX Documentation](https://networkx.org/)