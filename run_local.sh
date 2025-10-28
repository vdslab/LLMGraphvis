#!/bin/bash
set -e

echo "### Setting up environment file... ###"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file from .env.example"
else
    echo ".env file already exists."
fi

echo "### Configuring for local execution... ###"
# Use sed to replace DATABASE_URL for SQLite if the line exists, otherwise add it.
if grep -q "DATABASE_URL=" .env; then
    sed -i.bak 's|DATABASE_URL=.*|DATABASE_URL=sqlite:///./test.db|' .env
    echo "Updated DATABASE_URL to use SQLite."
else
    echo "DATABASE_URL=sqlite:///./test.db" >> .env
    echo "Added DATABASE_URL for SQLite."
fi

# Add or update NETWORKX_MCP_URL for local communication
if grep -q "NETWORKX_MCP_URL=" .env; then
    sed -i.bak 's|NETWORKX_MCP_URL=.*|NETWORKX_MCP_URL=http://localhost:8001|' .env
    echo "Updated NETWORKX_MCP_URL for local setup."
else
    echo "NETWORKX_MCP_URL=http://localhost:8001" >> .env
    echo "Added NETWORKX_MCP_URL for local setup."
fi
# Clean up backup file created by sed
rm -f .env.bak

# Get the Python version from .python-version
PYTHON_VERSION=$(cat .python-version)
echo "### Using Python version: $PYTHON_VERSION ###"

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null
then
    echo "pyenv could not be found. Please install pyenv to manage Python versions."
    exit 1
fi

# Initialize pyenv
eval "$(pyenv init --path)"
eval "$(pyenv init -)"

# Install and set up the correct Python version if not already present
if ! pyenv versions --bare | grep -q "^${PYTHON_VERSION}$"; then
    echo "Python ${PYTHON_VERSION} not found. Installing..."
    pyenv install ${PYTHON_VERSION}
fi
pyenv local ${PYTHON_VERSION}

echo "### Installing backend dependencies... ###"
echo "--- API dependencies ---"
(cd API && pip install -e .)
echo "--- NetworkXMCP dependencies ---"
(cd NetworkXMCP && pip install -e .)


echo "### Installing frontend dependencies... ###"
(cd frontend && npm install)

echo "### Starting backend services in the background... ###"
# Start NetworkXMCP
echo "--- Starting NetworkXMCP server on port 8001 ---"
(cd NetworkXMCP && PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port 8001 > ../networkxmcp.log 2>&1 &)
echo "NetworkXMCP PID: $!"

# Start API
echo "--- Starting API server on port 8000 ---"
(cd API && PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port 8000 > ../api.log 2>&1 &)
echo "API PID: $!"

echo "### Starting frontend development server... ###"
(cd frontend && npm run dev)

echo "### To stop the background services, run: 'kill %1 %2' or 'pkill -f uvicorn' ###"
