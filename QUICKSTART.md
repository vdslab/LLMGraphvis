# Quick Start Guide

## Prerequisites

- Docker and Docker Compose
- Google Gemini API key ([Get one here](https://ai.google.dev/))

## Setup

1. **Clone and navigate to the project**:
```bash
cd GraphVisAgent
```

2. **Set up environment variables**:

Create a `.env` file in the root directory:
```bash
# Backend
GOOGLE_API_KEY=your-gemini-api-key-here
DATABASE_URL=postgresql://postgres:postgres@db:5432/graphvisagent
SECRET_KEY=your-secret-key-here-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
NETWORKX_API_URL=http://networkx-api:8001

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=graphvisagent
```

3. **Start all services**:
```bash
docker compose up -d
```

This will start:
- Frontend (React + Vite) on http://localhost:5173
- Backend (FastAPI) on http://localhost:8000
- NetworkX API on http://localhost:8001
- PostgreSQL database on port 5432

4. **Wait for services to be ready** (about 30 seconds):
```bash
# Check if all services are running
docker compose ps

# Check backend logs
docker compose logs -f backend
```

## Using the Application

### 1. Access the Frontend
Open your browser and go to: http://localhost:5173

### 2. Register a New Account
- Click "Register"
- Enter a username and password
- Click "Register"

### 3. Create a New Chat
- Click "New Chat" button
- Enter a name like "My Network Analysis"
- Click "Create"

### 4. Upload a GraphML File
- You'll see an upload button in the center
- Click "Upload GraphML"
- Select a file from `sample_data/` (e.g., `karate_club.graphml`)
- Wait for the network to load (you'll see the graph appear)

### 5. Chat with the System
Try these example queries:

**English:**
```
Show people with many friends as larger
```

**Japanese:**
```
友達が多い人を大きく表示して
```

The system will:
1. Understand your request
2. Calculate degree centrality
3. Update the visualization with larger nodes for high-degree nodes
4. Respond with a confirmation message

### More Example Queries

**Betweenness Centrality (Bridge Nodes):**
```
Show bridge nodes as larger
橋渡しをしている人を大きく表示して
```

**Eigenvector Centrality (Influential Nodes):**
```
Show influential nodes with larger size
影響力のある人を大きく表示して
```

## Testing with the Script

Run the automated test:
```bash
python test_complete_flow.py
```

This will:
1. Register a test user
2. Create a chat
3. Upload the karate club network
4. Send a visualization request
5. Display the results

## API Documentation

Once the backend is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Troubleshooting

### Services won't start
```bash
# Check logs
docker compose logs

# Restart services
docker compose down
docker compose up -d
```

### Database connection errors
```bash
# Reset the database
docker compose down -v
docker compose up -d
```

### Frontend can't connect to backend
- Check that backend is running: http://localhost:8000/docs
- Check browser console for CORS errors
- Verify `.env` file has correct settings

### LLM not responding
- Verify `GOOGLE_API_KEY` is set correctly in `.env`
- Check backend logs: `docker compose logs backend`
- Ensure you have API quota available

### SSE connection issues
- Check browser console for errors
- Verify you're logged in
- Try refreshing the page

## Development Mode

### Backend Development
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### NetworkX API Development
```bash
cd networkx-api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Stopping the Application

```bash
# Stop all services
docker compose down

# Stop and remove volumes (resets database)
docker compose down -v
```

## Next Steps

- Read the [Implementation Guide](IMPLEMENTATION_GUIDE.md) for detailed architecture
- Check the [Specification](specification/README.md) for complete system design
- Explore sample networks in `sample_data/`
- Try different visualization queries

## Support

For issues or questions:
1. Check the logs: `docker compose logs`
2. Review the [Implementation Guide](IMPLEMENTATION_GUIDE.md)
3. Check the [Specification](specification/README.md)