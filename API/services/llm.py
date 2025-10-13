"""
LLM service for processing chat messages.
Supports multiple providers like Google Gemini and OpenAI.
"""

import os
import json
import httpx
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# --- Global state for dynamic reconfiguration ---
_current_provider = None
_gemini_client = None
_openai_client = None


def _initialize_clients():
    """Initialize LLM clients based on current environment variables."""
    global _current_provider, _gemini_client, _openai_client

    provider = os.environ.get("LLM_PROVIDER", "google").lower()
    _current_provider = provider

    # Reset clients
    _gemini_client = None
    _openai_client = None

    if provider == "google":
        if not os.environ.get("GOOGLE_API_KEY"):
            logger.warning(
                "LLM_PROVIDER is 'google', but GOOGLE_API_KEY environment variable is not set.")
            return
        try:
            from google import genai
            from google.genai import types
            _gemini_client = genai.Client()
            logger.info("Gemini client initialized successfully")
        except ImportError:
            logger.error(
                "Google GenAI SDK not installed. Please run 'pip install google-genai'")
        except Exception as e:
            logger.error(f"Error initializing Gemini client: {e}")

    elif provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            logger.warning(
                "LLM_PROVIDER is 'openai', but OPENAI_API_KEY environment variable is not set.")
            return
        try:
            from openai import OpenAI
            # Explicitly pass a default httpx client to avoid issues with proxy arguments
            _openai_client = OpenAI(http_client=httpx.Client())
            logger.info("OpenAI client initialized successfully")
        except ImportError:
            logger.error(
                "OpenAI SDK not installed. Please run 'pip install openai'")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {e}")
    else:
        logger.error(f"Unknown LLM_PROVIDER: {provider}")


def reload_llm_service():
    """Reload the LLM service with current environment variables."""
    logger.info("Reloading LLM service...")
    _initialize_clients()


def get_current_provider():
    """Get the current LLM provider."""
    return _current_provider


def get_clients():
    """Get the current LLM clients."""
    return _gemini_client, _openai_client


# Initialize clients on module load
_initialize_clients()

# --- Tool Definitions ---
# Shared tool definitions, adaptable for each provider.
TOOLS_DEFINITION = [
    {
        "name": "calculate_and_store_centrality",
        "description": "🔄 Calculate and store centrality values (Stage 1 of 2). Use this when the user asks for centrality visualization like 'show degree centrality', 'visualize by betweenness centrality', etc. This calculates the centrality values and prepares them for visualization. The system will automatically proceed to Stage 2 (visualization) after this completes.",
        "parameters": {
            "type": "object",
            "properties": {
                "centrality_type": {
                    "type": "string",
                    "description": "The type of centrality to calculate and visualize.",
                    "enum": ["degree", "closeness", "betweenness", "eigenvector", "pagerank", "katz"]
                },
                "centrality_params": {
                    "type": "object",
                    "description": "Optional parameters for centrality calculation.",
                    "properties": {
                        "max_iter": {
                            "type": "integer",
                            "description": "Maximum iterations for eigenvector/PageRank centrality",
                            "default": 1000
                        },
                        "alpha": {
                            "type": "number",
                            "description": "Alpha parameter for PageRank/Katz centrality",
                            "default": 0.85
                        }
                    }
                }
            },
            "required": ["centrality_type"]
        }
    },
    {
        "name": "get_centrality_visualization",
        "description": "🎨 Apply visualization to stored centrality data (Stage 2 of 2). Use this only when you have a calculation_id from Stage 1. This applies colors, sizes, and visual properties to the network based on calculated centrality values.",
        "parameters": {
            "type": "object",
            "properties": {
                "calculation_id": {
                    "type": "string",
                    "description": "The ID of the centrality calculation from Stage 1."
                },
                "color_scheme": {
                    "type": "string",
                    "description": "Color scheme for visualization.",
                    "enum": ["viridis", "plasma", "inferno", "magma", "simple", "blue_red", "cool_warm"],
                    "default": "viridis"
                },
                "size_range": {
                    "type": "array",
                    "description": "Node size range [min, max] for better node visibility.",
                    "items": {"type": "number"},
                    # Updated for much better visual distinction
                    "default": [10, 200]
                }
            },
            "required": ["calculation_id"]
        }
    },
    {
        "name": "list_centrality_calculations",
        "description": "📋 List all stored centrality calculations. Use this to see what centrality calculations are available for visualization.",
        "parameters": {}
    },
    {
        "name": "get_centrality_status",
        "description": "📊 Get status and details of a specific centrality calculation.",
        "parameters": {
            "type": "object",
            "properties": {
                "calculation_id": {
                    "type": "string",
                    "description": "The ID of the centrality calculation to check."
                }
            },
            "required": ["calculation_id"]
        }
    },
    {
        "name": "calculate_centrality",
        "description": "🧮 Calculate centrality values only (legacy single-stage). Use this when the user asks about node importance but doesn't need visualization - just the raw values.",
        "parameters": {
            "type": "object",
            "properties": {
                "centrality_type": {
                    "type": "string",
                    "description": "The type of centrality to calculate.",
                    "enum": ["degree", "closeness", "betweenness", "eigenvector", "pagerank", "katz"]
                },
                "centrality_params": {
                    "type": "object",
                    "description": "Optional parameters for centrality calculation."
                }
            },
            "required": ["centrality_type"]
        }
    },
    {
        "name": "calculate_and_store_layout",
        "description": "🔄 Calculate and store layout positions (Stage 1 of 2). Use this when the user asks for layout changes like 'change to spring layout', 'apply circular layout', etc. This calculates the layout positions and prepares them for visualization. The system will automatically proceed to Stage 2 (rendering) after this completes.",
        "parameters": {
            "type": "object",
            "properties": {
                "layout_type": {
                    "type": "string",
                    "description": "The type of layout algorithm to use.",
                    "enum": ["spring", "kamada_kawai", "circular", "random", "shell", "spectral", "planar", "spiral", "bipartite", "multipartite"]
                },
                "layout_params": {
                    "type": "object",
                    "description": "Optional parameters for layout calculation.",
                    "properties": {
                        "k": {
                            "type": "number",
                            "description": "Optimal distance between nodes (for spring layout)"
                        },
                        "iterations": {
                            "type": "integer",
                            "description": "Maximum number of iterations (for spring layout)",
                            "default": 50
                        },
                        "scale": {
                            "type": "number",
                            "description": "Scale factor for positions",
                            "default": 1
                        },
                        "seed": {
                            "type": "integer",
                            "description": "Random seed for reproducible layouts"
                        }
                    }
                }
            },
            "required": ["layout_type"]
        }
    },
    {
        "name": "get_layout_visualization_data",
        "description": "🎨 Get layout visualization data (Stage 2 of 2). Use this only when you have a calculation_id from Stage 1. This prepares the complete layout data for Cytoscape.js rendering.",
        "parameters": {
            "type": "object",
            "properties": {
                "calculation_id": {
                    "type": "string",
                    "description": "The ID of the layout calculation from Stage 1."
                }
            },
            "required": ["calculation_id"]
        }
    },
    {
        "name": "list_available_layouts",
        "description": "📋 List all available layout algorithms with descriptions and parameters. Use this to help users choose appropriate layout algorithms.",
        "parameters": {}
    },
    {
        "name": "get_layout_parameters_info",
        "description": "ℹ️ Get detailed parameter information for a specific layout algorithm.",
        "parameters": {
            "type": "object",
            "properties": {
                "layout_type": {
                    "type": "string",
                    "description": "The layout algorithm to get parameter info for.",
                    "enum": ["spring", "kamada_kawai", "circular", "random", "shell", "spectral", "planar", "spiral", "bipartite", "multipartite"]
                }
            },
            "required": ["layout_type"]
        }
    },
    {
        "name": "get_network_info",
        "description": "📊 Retrieve basic statistics about the network, such as the number of nodes and edges, density, etc.",
        "parameters": {}
    },
]

# --- System Prompt ---
SYSTEM_PROMPT = """
You are an expert network analysis assistant. Your role is to help users analyze and visualize network graphs.
You have access to a set of tools to perform network operations. When a user asks a question or gives a command, first determine if it can be answered by calling one of your tools.

**🎯 Enhanced Two-Stage System for Network Visualization:**

**🔄 Centrality Visualization Process:**
When users ask for centrality visualization (e.g., "show degree centrality", "visualize with betweenness centrality", "次数中心性で可視化して"), ALWAYS use the two-stage process:

1. **🔄 Stage 1 - Calculate and Store:** Use `calculate_and_store_centrality` to compute centrality values
   - This calculates the centrality and returns a calculation_id
   - The system automatically proceeds to Stage 2

2. **🎨 Stage 2 - Visualize:** The system automatically calls `get_centrality_visualization`
   - This applies colors, sizes, and visual properties to nodes
   - Users will see immediate visual changes in the network

**🔄 Layout Modification Process:**
When users ask for layout changes (e.g., "change to spring layout", "apply circular layout", "レイアウトを変更して"), ALWAYS use the two-stage process:

1. **🔄 Stage 1 - Calculate and Store:** Use `calculate_and_store_layout` to compute layout positions
   - This calculates the layout positions and returns a calculation_id
   - The system automatically proceeds to Stage 2

2. **🎨 Stage 2 - Render:** The system automatically calls `get_layout_visualization_data`
   - This prepares the complete layout data for Cytoscape.js rendering
   - Users will see immediate visual changes in the network arrangement

**🔑 Key Phrases for Centrality Visualization:**
- "visualize by [centrality]" → use calculate_and_store_centrality
- "show [centrality] centrality" → use calculate_and_store_centrality  
- "color nodes by [centrality]" → use calculate_and_store_centrality
- "次数中心性で可視化" → use calculate_and_store_centrality with "degree"
- "中心性を表示" → use calculate_and_store_centrality

**🔑 Key Phrases for Layout Changes:**
- "change to [layout] layout" → use calculate_and_store_layout
- "apply [layout] layout" → use calculate_and_store_layout
- "use [layout] algorithm" → use calculate_and_store_layout
- "レイアウトを変更" → use calculate_and_store_layout
- "春力学モデル" → use calculate_and_store_layout with "spring"

**🎨 Available Centrality Types:**
- **degree**: How many connections a node has (local importance)
- **betweenness**: How often a node lies on shortest paths (bridge importance)
- **closeness**: How close a node is to all other nodes (global accessibility)
- **eigenvector**: Importance based on connected nodes' importance (recursive importance)
- **pagerank**: Google's PageRank algorithm (authoritative importance)
- **katz**: Similar to eigenvector with baseline importance

**🎨 Available Layout Types:**
- **spring**: Force-directed layout using Fruchterman-Reingold algorithm (good for most networks)
- **kamada_kawai**: Spring-model layout with global optimization (high-quality for small-medium networks)
- **circular**: Position nodes in a circle (good for highlighting structure)
- **random**: Position nodes randomly (testing/initial positioning)
- **shell**: Position nodes in concentric circles (hierarchical networks)
- **spectral**: Position using eigenvectors of graph Laplacian (community detection)
- **planar**: Position for planar graphs without edge crossings (tree structures)
- **spiral**: Position nodes in spiral pattern (time series networks)
- **bipartite**: Position in two columns for bipartite graphs (two-mode networks)
- **multipartite**: Position in multiple layers (multilayer networks)

**🎨 Visual Color Schemes:**
- viridis (default): Purple to yellow gradient
- plasma: Purple to pink to yellow
- inferno: Black to yellow through purple/red
- magma: Black to white through purple/pink
- simple: Blue to red spectrum
- blue_red: Cool blue to warm red
- cool_warm: Scientific blue-white-red

**📋 Other Tools:**
- `list_centrality_calculations`: See all stored centrality calculations
- `get_centrality_status`: Check specific centrality calculation details
- `calculate_centrality`: Get raw centrality values (no visualization)
- `list_available_layouts`: See all available layout algorithms
- `get_layout_parameters_info`: Get detailed layout parameter information
- `get_network_info`: Get network statistics

**🎭 Interaction Flow:**

1. **Analyze User Request:** Understand what they want to do
2. **Tool Selection:** Choose the appropriate tool based on their intent
3. **Two-Stage Processing:** For visualization/layout, use calculate_and_store_* (Stage 2 is automatic)
4. **Helpful Responses:** Provide informative feedback about what was done

**⚡ Quick Examples:**
- User: "show degree centrality" → call calculate_and_store_centrality with centrality_type="degree"
- User: "change to spring layout" → call calculate_and_store_layout with layout_type="spring"
- User: "apply circular layout" → call calculate_and_store_layout with layout_type="circular"
- User: "次数中心性で可視化して" → call calculate_and_store_centrality with centrality_type="degree"
- User: "レイアウトを変更して" → ask what layout they prefer, then call calculate_and_store_layout

Always be helpful, informative, and explain what the centrality measure or layout algorithm means and what the visualization shows!
"""


async def _process_with_gemini(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Process messages using Google Gemini."""
    gemini_client, _ = get_clients()
    if not gemini_client:
        return {"content": "Error: Gemini client is not initialized."}

    try:
        from google.genai import types
    except ImportError:
        return {"content": "Error: Google GenAI SDK not available."}

    gemini_history = []
    for msg in messages:
        role = "user" if msg["role"] in ["user", "tool"] else "model"
        gemini_history.append(types.Content(
            role=role, parts=[types.Part.from_text(text=msg["content"])]))

    user_prompt = gemini_history.pop().parts[0].text

    try:
        # Gemini用にツール定義を変換
        gemini_tools = []
        for tool in TOOLS_DEFINITION:
            gemini_tool = {
                "function_declarations": [
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"]
                    }
                ]
            }
            gemini_tools.append(gemini_tool)

        chat = gemini_client.chats.create(
            model="gemini-2.5-pro", history=gemini_history)
        response = chat.send_message(
            user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, tools=gemini_tools)
        )

        if response.function_calls:
            function_call = response.function_calls[0]
            return {
                "tool_calls": [{
                    "function": {
                        "name": function_call.name,
                        "arguments": dict(function_call.args)
                    }
                }]
            }
        else:
            return {"content": response.text}
    except Exception as e:
        print(f"Error with Gemini: {e}")
        return {"content": f"Error with Gemini: {e}"}


async def _process_with_openai(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Process messages using OpenAI."""
    _, openai_client = get_clients()
    if not openai_client:
        return {"content": "Error: OpenAI client is not initialized."}

    # Adapt history for OpenAI format
    openai_history = []
    for msg in messages:
        if msg["role"] == "tool":
            openai_history.append({"role": "tool", "tool_call_id": "placeholder_id",
                                  "name": "tool_name", "content": msg["content"]})
        else:
            openai_history.append(
                {"role": msg["role"], "content": msg["content"]})

    try:
        response = openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}
                      ] + openai_history,
            tools=[{"type": "function", "function": f}
                   for f in TOOLS_DEFINITION],
            tool_choice="auto",
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            # OpenAI can return multiple tool calls, we'll take the first one for simplicity
            tool_call = tool_calls[0]
            return {
                "tool_calls": [{
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    }
                }]
            }
        else:
            return {"content": response_message.content}
    except Exception as e:
        print(f"Error with OpenAI: {e}")
        return {"content": f"Error with OpenAI: {e}"}


async def process_chat_message(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Process chat messages by routing to the configured LLM provider.
    """
    provider = get_current_provider()
    print(f"Processing message with provider: {provider}")
    if provider == "openai":
        return await _process_with_openai(messages)
    elif provider == "google":
        return await _process_with_gemini(messages)
    else:
        return {"content": f"Error: Unknown LLM_PROVIDER '{provider}'. Please set to 'google' or 'openai'."}


async def _process_with_openai(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Process messages using OpenAI."""
    if not openai_client:
        return {"content": "Error: OpenAI client is not initialized."}

    # Adapt history for OpenAI format
    openai_history = []
    for msg in messages:
        if msg["role"] == "tool":
            openai_history.append({"role": "tool", "tool_call_id": "placeholder_id",
                                  "name": "tool_name", "content": msg["content"]})
        else:
            openai_history.append(
                {"role": msg["role"], "content": msg["content"]})

    try:
        response = openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}
                      ] + openai_history,
            tools=[{"type": "function", "function": f}
                   for f in TOOLS_DEFINITION],
            tool_choice="auto",
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            # OpenAI can return multiple tool calls, we'll take the first one for simplicity
            tool_call = tool_calls[0]
            return {
                "tool_calls": [{
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    }
                }]
            }
        else:
            return {"content": response_message.content}
    except Exception as e:
        print(f"Error with OpenAI: {e}")
        return {"content": f"Error with OpenAI: {e}"}


async def process_chat_message(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Process chat messages by routing to the configured LLM provider.
    """
    provider = os.environ.get("LLM_PROVIDER", "google").lower()
    print(f"Processing message with provider: {provider}")
    if provider == "openai":
        return await _process_with_openai(messages)
    elif provider == "google":
        return await _process_with_gemini(messages)
    else:
        return {"content": f"Error: Unknown LLM_PROVIDER '{provider}'. Please set to 'google' or 'openai'."}
