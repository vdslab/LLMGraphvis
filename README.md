# GraphVisAgent

A web application for interactive network visualization powered by LLM (Gemini API). Users can upload GraphML files, visualize networks, and interact with them using natural language.

## 🚀 Quick Start

**Get started in 5 minutes!** See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

```bash
# 1. Set your Gemini API key
export GOOGLE_API_KEY="your-api-key-here"

# 2. Start all services
docker compose up -d

# 3. Open your browser
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

## ✨ Features

- 🔐 **User Authentication** - Secure login and registration
- 📤 **GraphML Upload** - Import network data from GraphML files
- 🤖 **LLM-Powered Chat** - Natural language interaction using Gemini API
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
                    │ Gemini API  │
                    └─────────────┘
```

### Components

- **Frontend**: React + Vite, D3.js for visualization
- **Backend**: FastAPI with Gemini API integration
- **NetworkX API**: Network analysis and centrality calculations
- **Database**: PostgreSQL for data persistence

## 📚 Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Get up and running in minutes
- **[Implementation Guide](IMPLEMENTATION_GUIDE.md)** - Detailed architecture and API documentation
- **[Specification](specification/README.md)** - Complete system specification (Japanese)

## 🛠️ Technology Stack

### Backend
- FastAPI (Python web framework)
- Google GenAI SDK (`google-genai`) for Gemini API
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

### LLM Integration (Gemini API)

The system uses **Gemini 2.5 Flash** with **function calling** to understand user requests and execute appropriate network analysis tools:

```python
# Example: User says "Show people with many friends as larger"
# LLM automatically:
1. Calls calculate_centrality(network_id, "degree")
2. Calls generate_visualization(node_size_attribute="degree_centrality")
3. Returns a friendly response
```

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

### Automated Test
```bash
python test_complete_flow.py
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
- Python 3.11+
- Node.js 18+
- Google Gemini API key

### Environment Variables

Create a `.env` file:
```env
GOOGLE_API_KEY=your-gemini-api-key
DATABASE_URL=postgresql://postgres:postgres@db:5432/graphvisagent
SECRET_KEY=your-secret-key
NETWORKX_API_URL=http://networkx-api:8001
```

### Running Locally

**With Docker:**
```bash
docker compose up -d
```

**Without Docker:**
```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Terminal 2: NetworkX API
cd networkx-api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Terminal 3: Frontend
cd frontend
npm install
npm run dev
```

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

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for complete API documentation.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- Built with [Gemini API](https://ai.google.dev/gemini-api/docs)
- Network analysis powered by [NetworkX](https://networkx.org/)
- Visualization using [D3.js](https://d3js.org/)

## 📞 Support

For issues or questions:
1. Check the [Implementation Guide](IMPLEMENTATION_GUIDE.md)
2. Review the [Quick Start Guide](QUICKSTART.md)
3. Check the logs: `docker compose logs`

---

**Made with ❤️ using Gemini API**