# System Knowledge Base

## System Architecture

The graph visualization system consists of three main components:
1.  **Frontend (React/Vite)**: Handles user interaction, chat interface, and graph visualization (using d3.js/canvas). Communicates with Backend via REST and SSE.
2.  **Backend (FastAPI)**: Manages chat sessions, message persistence, and orchestrates the LLM (Gemini) and Tools.
3.  **NetworkX API (MCP Server)**: A specialized service providing graph algorithms (NetworkX) and data management as an MCP (Model Context Protocol) server.

## Core Principles (Agent Policy)
*Updated: 2025-12-25*

1.  **Chat-Based Visual Analytics**:
    -   The system replaces WIMP interfaces with Chat-driven operations.
    -   The Agent acts as the operational engine, translating intent into tool calls.

2.  **Minimalism & Precision**:
    -   **Rule**: Do ONLY what is explicitly requested for specific analysis tasks.
    -   **Example**: "Analyze largest component" -> Create Subgraph + Layout. (No auto-coloring).
    -   **Visuals**: Default to Uniform colors/sizes unless mapping is requested or essential.

3.  **User Agency**:
    -   Propose visual mappings before applying them.
    -   Respect `visual_state` (don't override user's view without reason).
        -   **Check State First**: Before modifying visuals, always use `get_visualization_state` to know what the user is seeing.
        -   **Partial Updates**: Use specialized tools (`update_node_color`, `update_node_size`, `update_layout`) for precise visual adjustments. These are preferred over `generate_visualization` for simple interactions as they preserve other visual states implicitly.
        -   **Full Resets**: Use `generate_visualization` when you need to change multiple aspects (color + size + layout) simultaneously or reset the view.
    -   **Navigation**:
        - Use `switch_to_network` to return to previous graphs (e.g., "Main graph"). This preserves their last seen state.
        - **Layout Inheritance**: Subgraphs automatically inherit the parent's layout and visual settings by default (`preserve_layout=True`), ensuring visual continuity.

4.  **Verification**:
    -   Agent is encouraged to run intermediate tools (e.g., `get_node_attributes`) to verify data existence before operations.

## Current status
-   **Active Development**: Refining LLM behaviors for reliability (Lazy Tool Fixes) and precision (Minimalism).
-   **Key Documents**:
    -   `GEMINI.md`: Agent Instructions & Dev Guidelines.
    -   `specification/`: detailed technical specs.
