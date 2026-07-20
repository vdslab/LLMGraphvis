from abc import ABC, abstractmethod
from typing import AsyncIterator, List

from .types import LLMMessage, StreamChunk, ToolDefinition


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    def supports_native_thinking(self) -> bool:
        """Whether this provider/model surfaces reasoning via a native "thinking"
        stream (StreamChunk.thought) rather than requiring the model to write
        literal <thought> tags in its regular text output.

        The engine uses this to decide which system-prompt variant to send:
        providers with native thinking must NOT also be asked to hand-write
        <thought> tags in-band, since the engine already captures and renders
        their native thinking through the same UI path, and asking for both
        produces duplicated/conflicting output.
        """
        return False

    @abstractmethod
    def generate(
        self,
        history: List[LLMMessage],
        tools: List[ToolDefinition],
        system_instruction: str,
    ) -> AsyncIterator[StreamChunk]:
        """Return an async iterator of StreamChunks for a single generation."""
        pass
