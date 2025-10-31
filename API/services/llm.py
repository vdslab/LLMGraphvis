"""
LLM service for processing chat messages.
Supports multiple providers like Google Gemini and OpenAI.
"""

import os
import json
import httpx
from typing import List, Dict, Any

# --- Provider Selection ---
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "google").lower()

# --- Client Initialization ---
gemini_client = None
openai_client = None

if LLM_PROVIDER == "google":
    if not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("LLM_PROVIDER is 'google', but GOOGLE_API_KEY environment variable is not set.")
    try:
        from google import genai
        from google.genai import types
        gemini_client = genai.Client()
    except ImportError:
        print("Google GenAI SDK not installed. Please run 'pip install google-genai'")
        gemini_client = None
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        gemini_client = None

elif LLM_PROVIDER == "openai":
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("LLM_PROVIDER is 'openai', but OPENAI_API_KEY environment variable is not set.")
    try:
        from openai import OpenAI
        # Explicitly pass a default httpx client to avoid issues with proxy arguments
        openai_client = OpenAI(http_client=httpx.Client())
    except ImportError:
        print("OpenAI SDK not installed. Please run 'pip install openai'")
        openai_client = None
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        openai_client = None

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

async def _process_with_gemini(messages: List[Dict[str, str]], model_name: str = "gemini-2.5-flash") -> Dict[str, Any]:
    """
    Processes a list of messages using the Google Gemini API.

    Args:
        messages: A list of messages in the conversation history.
        model_name: The name of the Gemini model to use.

    Returns:
        A dictionary containing the response from the Gemini API.
    """
    if not gemini_client:
        return {"content": "Error: Gemini client is not initialized."}

    gemini_history = []
    for msg in messages:
        role = "user" if msg["role"] in ["user", "tool"] else "model"
        gemini_history.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    
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

        chat = gemini_client.chats.create(model=model_name, history=gemini_history)
        response = chat.send_message(
            user_prompt,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=gemini_tools)
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
    """
    Processes a list of messages using the OpenAI API.

    Args:
        messages: A list of messages in the conversation history.

    Returns:
        A dictionary containing the response from the OpenAI API.
    """
    if not openai_client:
        return {"content": "Error: OpenAI client is not initialized."}

    # Adapt history for OpenAI format
    openai_history = []
    for msg in messages:
        if msg["role"] == "tool":
            openai_history.append({"role": "tool", "tool_call_id": "placeholder_id", "name": "tool_name", "content": msg["content"]})
        else:
            openai_history.append({"role": msg["role"], "content": msg["content"]})
    
    try:
        response = openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + openai_history,
            tools=[{"type": "function", "function": f} for f in TOOLS_DEFINITION],
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


ALLOWED_GEMINI_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

async def process_chat_message(messages: List[Dict[str, str]], model: str = "gemini-2.5-flash") -> Dict[str, Any]:
    """
    Processes a chat message using the configured LLM provider.

    Args:
        messages: A list of messages in the conversation history.
        model: The name of the model to use.

    Returns:
        A dictionary containing the response from the LLM provider.
    """
    print(f"Processing message with provider: {LLM_PROVIDER}")
    if LLM_PROVIDER == "openai":
        # OpenAIのモデル選択も同様に拡張可能
        return await _process_with_openai(messages)
    elif LLM_PROVIDER == "google":
        if model not in ALLOWED_GEMINI_MODELS:
            # 安全なデフォルト値にフォールバック
            model = "gemini-2.5-flash"
            print(f"Warning: Invalid model '{model}' requested. Falling back to default 'gemini-2.5-flash'.")
        return await _process_with_gemini(messages, model_name=model)
    else:
        return {"content": f"Error: Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Please set to 'google' or 'openai'."}
