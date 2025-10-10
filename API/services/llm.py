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
        "name": "calculate_centrality",
        "description": "Calculates a specified centrality metric for the network. Use this when the user asks about node importance, influence, or connectivity.",
        "parameters": {
            "type": "object",
            "properties": {
                "centrality_type": {
                    "type": "string",
                    "description": "The type of centrality to calculate.",
                    "enum": ["degree", "closeness", "betweenness", "eigenvector", "pagerank"]
                },
            },
            "required": ["centrality_type"]
        }
    },
    {
        "name": "change_layout",
        "description": "Changes the visual layout of the network graph.",
        "parameters": {
            "type": "object",
            "properties": {
                "layout_type": {
                    "type": "string",
                    "description": "The layout algorithm to apply.",
                    "enum": ["spring", "circular", "random", "spectral", "shell", "kamada_kawai", "fruchterman_reingold"]
                }
            },
            "required": ["layout_type"]
        }
    },
    {
        "name": "get_network_info",
        "description": "Retrieves basic statistics about the network, such as the number of nodes and edges, density, etc.",
        "parameters": {}
    },
]

# --- System Prompt ---
SYSTEM_PROMPT = """
You are an expert network analysis assistant. Your role is to help users analyze and visualize network graphs.
You have access to a set of tools to perform network operations. When a user asks a question or gives a command, first determine if it can be answered by calling one of your tools.

**Interaction Flow:**

1.  **Analyze User Request:** Understand the user's intent.
2.  **Tool Selection:** If the request matches a tool's capability, you should respond with a tool call.
3.  **General Conversation:** If the user's message is a greeting or a question that cannot be answered by a tool, respond in a helpful and conversational manner.

**Your Final Output should be either a direct text response OR a tool call.**
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
