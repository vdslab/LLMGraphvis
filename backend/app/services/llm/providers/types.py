from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class ToolDefinition:
    """Provider-agnostic tool definition."""
    name: str
    description: str
    parameters: Dict  # JSON Schema object


@dataclass
class FunctionCallData:
    """A function call emitted by the LLM during streaming."""
    name: str
    args: Dict[str, Any]
    call_id: Optional[str] = None  # Required by Anthropic for tool_use/tool_result pairing


@dataclass
class UsageData:
    """Token usage reported by a provider for a single generate() call."""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


@dataclass
class StreamChunk:
    """A single normalized event from the LLM stream."""
    text: Optional[str] = None
    thought: Optional[str] = None
    function_calls: List[FunctionCallData] = field(default_factory=list)
    usage: Optional[UsageData] = None


# --- History message part types ---

@dataclass
class LLMTextPart:
    text: str


@dataclass
class LLMFunctionCallPart:
    name: str
    args: Dict[str, Any]
    call_id: Optional[str] = None


@dataclass
class LLMFunctionResponsePart:
    name: str
    response: Any
    call_id: Optional[str] = None  # Must match the corresponding LLMFunctionCallPart.call_id


LLMPart = Union[LLMTextPart, LLMFunctionCallPart, LLMFunctionResponsePart]


@dataclass
class LLMMessage:
    """Provider-agnostic conversation history entry."""
    role: str  # "user" | "model" | "tool"
    parts: List[LLMPart]
