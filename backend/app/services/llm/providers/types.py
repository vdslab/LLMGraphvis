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
    call_id: Optional[str] = None
    thought_signature: Optional[bytes] = None


@dataclass
class UsageData:
    """Token usage of one or more generate() calls, normalized across providers.

    Providers report these numbers differently (Anthropic excludes cache reads
    and writes from `input_tokens`, Gemini excludes thinking from its output
    count); each adapter converts to this one meaning so totals are comparable
    and `pricing.estimate_cost_usd` needs no per-provider formula. See ADR 0025.

    - input_tokens: every prompt token, cache reads and cache writes included.
    - cached_input_tokens: the part of input_tokens read from the prompt cache.
    - cache_write_tokens: the part of input_tokens written to the prompt cache.
    - output_tokens: every generated token, reasoning included.
    - reasoning_tokens: the part of output_tokens spent on reasoning, when the
      provider reports it separately (Anthropic does not; it stays 0).
    """
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0

    def add(self, other: "UsageData") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_input_tokens += other.cached_input_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.reasoning_tokens += other.reasoning_tokens

    @property
    def is_empty(self) -> bool:
        return not (self.input_tokens or self.output_tokens)

    def as_dict(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }


@dataclass
class TurnUsage(UsageData):
    """Usage summed over an agent turn, plus one entry per generate() call."""
    calls: List[Dict[str, int]] = field(default_factory=list)

    def add_call(self, usage: UsageData) -> None:
        self.add(usage)
        self.calls.append(usage.as_dict())


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
    thought_signature: Optional[bytes] = None


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
