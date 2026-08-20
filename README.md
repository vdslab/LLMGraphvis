# GraphVisAgent

A web application for interactive network visualization driven by an LLM agent. Users upload GraphML files and drive all analysis and visual encoding through conversation.

## 🚀 Quick Start

See [QUICKSTART.md](QUICKSTART.md) for full setup instructions.

```bash
# 1. Configure your environment (set SECRET_KEY, LLM_PROVIDER and its API key)
cp .env.sample .env

# 2. Start all services
docker compose up -d

# 3. Open your browser
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

## ✨ Features

- 🔐 **User Authentication** - Secure login and registration
- 📤 **GraphML Upload** - Import network data from GraphML files
- 🤖 **LLM-Powered Chat** - Natural language interaction; swap between cloud and local models per chat
- 📊 **Interactive Visualization** - Real-time network visualization
- 🎯 **Smart Analysis** - Automatic centrality calculation and visual mapping
- 🔄 **Real-time Updates** - Server-Sent Events for live feedback

## 🎯 Example Usage

1. **Upload a network**: Upload a GraphML file (e.g., social network, citation network)
2. **Chat with the system**:
   - "友達が多い人を大きく表示して" (Show people with many friends as larger)
   - "橋渡しをしている人を大きく表示して" (Show bridge nodes as larger)
   - "影響力のある人を大きく表示して" (Show influential people as larger)
3. **See the results**: The visualization updates automatically based on your request

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Frontend  │────▶│   Backend   │────▶│ NetworkX API │
│ (React+Vite)│◀────│  (FastAPI)  │◀────│  (FastAPI)   │
└─────────────┘     └─────────────┘     └──────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  PostgreSQL │
                    └─────────────┘
                           ▲
                           │
                    ┌─────────────┐
                    │  LLM (any)  │
                    └─────────────┘
```

### Components

- **Frontend**: React + Vite, D3.js for visualization
- **Backend**: FastAPI, agent loop over a pluggable LLM provider
- **NetworkX API**: Network analysis and centrality calculations
- **Database**: PostgreSQL for data persistence

## 📚 Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Setup, usage, and troubleshooting
- **[AGENTS.md](AGENTS.md)** - How the repository is organised and how to change it
- **[Specification](specification/README.md)** - The design decisions behind the system (Japanese)
- **API reference** - http://localhost:8000/docs once the backend is running

## 🛠️ Technology Stack

### Backend
- FastAPI (Python web framework)
- Pluggable LLM providers: Google Gemini, Anthropic Claude, OpenAI, and LM Studio (local)
- SQLAlchemy (ORM)
- PostgreSQL (Database)
- NetworkX (Graph analysis)

### Frontend
- React 18
- Vite (Build tool)
- D3.js (Visualization)
- Zustand (State management)
- Axios (HTTP client)

## 🔑 Key Features Explained

### LLM Integration

The agent uses **tool calling** to turn a request into network analysis. Providers
are pluggable — Google Gemini, Anthropic Claude, OpenAI, and LM Studio for local
models — and the provider and model are remembered per chat.

```
# User: "Show people with many friends as larger"
# The agent:
1. analysis_degree_centrality(...)      # compute and store the metric
2. visualization_generate(...)          # map it to node size and render
3. Explains what it did, and why
```

Tools are served over MCP by the NetworkX API service and discovered
automatically; see [AGENTS.md](AGENTS.md).

### Real-time Updates (SSE)

All operations use Server-Sent Events for real-time feedback:
- Upload progress
- LLM thinking process
- Tool execution status
- Visualization updates

### Network Analysis Tools

Available centrality metrics:
- **Degree Centrality**: Number of connections
- **Betweenness Centrality**: Bridge nodes
- **Closeness Centrality**: Average distance to others
- **Eigenvector Centrality**: Influence based on connections

## 🧪 Testing

```bash
cd backend       && pytest
cd networkx-api  && pytest tests
cd frontend      && npm test && npm run lint
```

### Manual Testing
1. Start the services: `docker compose up -d`
2. Open http://localhost:5173
3. Register/Login
4. Create a chat
5. Upload a GraphML file from `sample_data/`
6. Try example queries

## 📁 Sample Data

The `sample_data/` directory contains example networks:
- `karate_club.graphml` - Zachary's Karate Club network
- `star_graph.graphml` - Simple star topology
- `random_graph.graphml` - Random network
- `directed_graph.graphml` - Directed network example

## 🔧 Development

### Prerequisites
- Docker and Docker Compose
- An API key for one LLM provider, or LM Studio running locally

### Environment Variables

Copy `.env.sample` to `.env` and fill it in — it documents every variable,
including the provider keys and the container egress switches.

```bash
cp .env.sample .env
```

### Running Locally

**With Docker:**
```bash
docker compose up -d
```

**Without Docker:** `scripts/local/start.sh` runs the whole stack on macOS. To
run one service at a time, see [QUICKSTART.md](QUICKSTART.md#running-without-docker).

### Using a local model with LM Studio

GraphVisAgent can use LM Studio's OpenAI-compatible Chat Completions endpoint,
including streaming and tool calls.

1. In LM Studio, load a model with tool-use support and start the server from
   the **Developer** tab (the default port is `1234`).
2. Restart the backend and open the model selector. GraphVisAgent reads
   `GET /api/v1/models` and lists the chat-capable models available in LM Studio.
3. Optionally set a model to use when a chat has no pinned model:

   ```env
   # Optional LM Studio default; the selector does not require this setting.
   LM_STUDIO_MODEL=your-default-model-id
   # Optional when LM Studio server authentication is enabled:
   # LM_STUDIO_API_KEY=your-lm-studio-token
   ```

4. Select **LM Studio (Local)** and the desired model in each chat. Set
   `LLM_PROVIDER=lmstudio` only when LM Studio should be the process-wide
   default provider; multiple providers remain available in the selector.

When the backend runs directly on the host, it connects to
`http://localhost:1234/v1`. Docker Compose automatically uses
`http://host.docker.internal:1234/v1`; override `LM_STUDIO_BASE_URL` if LM
Studio is served elsewhere. Models with native tool-use support give the most
reliable graph-agent behavior.

## 🌐 API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/token` - Login
- `GET /api/auth/users/me` - Get current user

### Chat
- `GET /api/chat` - List all chats
- `POST /api/chat` - Create new chat
- `POST /api/chat/{id}/upload` - Upload GraphML
- `POST /api/chat/{id}/process` - Process message
- `GET /api/chat/{id}/stream` - SSE stream

The complete, always-current reference is the OpenAPI schema at
http://localhost:8000/docs.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- Tools exposed over the [Model Context Protocol](https://modelcontextprotocol.io/)
- Network analysis powered by [NetworkX](https://networkx.org/)
- Visualization using [D3.js](https://d3js.org/)

## 📞 Support

For issues or questions:
1. Review the [Quick Start Guide](QUICKSTART.md)
2. Check the logs: `docker compose logs`
