# Network Visualization API

This project provides a comprehensive platform for network visualization and analysis. It features a FastAPI backend, a React-based frontend, and a separate service for handling computationally intensive tasks with NetworkX.

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Docker Setup (Recommended)](#docker-setup-recommended)
  - [Local Setup](#local-setup)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)

## Project Overview

The Network Visualization API allows users to upload network data, visualize it using various layout algorithms, and interactively analyze network properties through a chat-based interface. The project is designed to be modular and scalable, with a clear separation of concerns between the frontend, backend, and analysis services.

## Features

- **Network Visualization**: Upload GraphML files and visualize them as interactive graphs.
- **Layout Algorithms**: Apply various layout algorithms, including Spring, Circular, Spectral, and more.
- **Chat-Based Analysis**: Interact with the network using natural language commands to perform analysis and modify visualizations.
- **User Authentication**: Secure user accounts with JWT-based authentication.
- **Stateful Analysis**: The NetworkXMCP service provides stateful network analysis with caching for improved performance.

## System Architecture

The project consists of three main services:

- **`frontend`**: A React-based single-page application that provides the user interface for network visualization and chat.
- **`API`**: A FastAPI backend that handles user authentication, data storage, and communication with the `NetworkXMCP` service.
- **`NetworkXMCP`**: A separate FastAPI service that performs computationally intensive network analysis tasks using NetworkX.

These services are designed to be run in separate containers using Docker Compose, but they can also be run locally for development.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js and npm (for local frontend setup)
- Python 3.10+ and pip (for local backend setup)

### Docker Setup (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/vdslab/LLMGraphvis.git
    cd LLMGraphvis
    ```

2.  **Create an environment file:**
    ```bash
    cp .env.example .env
    ```

3.  **Build and start the services:**
    ```bash
    docker compose up --build
    ```

The frontend will be available at `http://localhost:3000`, and the API will be at `http://localhost:8000`.

### Local Setup

1.  **Backend (`API` and `NetworkXMCP`)**
    - Navigate to the `API` and `NetworkXMCP` directories and install the dependencies:
      ```bash
      cd API
      pip install -r requirements.txt
      cd ../NetworkXMCP
      pip install -r requirements.txt
      ```
    - Run the services:
      ```bash
      uvicorn main:app --host 0.0.0.0 --port 8000
      uvicorn main:app --host 0.0.0.0 --port 8001
      ```

2.  **Frontend**
    - Navigate to the `frontend` directory and install the dependencies:
      ```bash
      cd frontend
      npm install
      ```
    - Start the development server:
      ```bash
      npm start
      ```

## Usage

Once the application is running, you can:

1.  **Register a new account** or **log in** with an existing one.
2.  **Upload a network file** in GraphML format using the "Upload Network File" button.
3.  **Interact with the network** through the chat interface. For example, you can ask the chatbot to "apply a circular layout" or "calculate the betweenness centrality."
4.  **Explore the network visualization**, which will update in real-time based on your chat commands.

## API Endpoints

The FastAPI backend provides a RESTful API for managing users, networks, and chat conversations. For more details, you can access the interactive API documentation at `http://localhost:8000/docs`.

## Project Structure

```
.
├── API/                # FastAPI backend service
├── frontend/           # React frontend application
├── NetworkXMCP/        # NetworkX analysis service
├── docker-compose.yml  # Docker Compose configuration
└── README.md           # This file
```
